import asyncio
from typing import (
    AsyncIterator,
    Iterable,
    Tuple,
)

from lahja import EndpointAPI

from cancel_token import CancelToken
from eth.abc import DatabaseAPI
from eth.constants import GENESIS_PARENT_HASH, MAX_UNCLE_DEPTH
from eth.db.backends.base import BaseAtomicDB
from eth.exceptions import (
    HeaderNotFound,
)
from eth.rlp.blocks import BaseBlock
from eth.rlp.headers import BlockHeader
from eth.rlp.transactions import BaseTransaction
from eth_typing import (
    Hash32,
    BlockNumber,
)
from eth_utils import (
    ValidationError,
)
import rlp

from p2p.service import BaseService

from trinity.chains.base import AsyncChainAPI
from trinity.db.eth1.chain import BaseAsyncChainDB
from trinity.db.eth1.header import BaseAsyncHeaderDB
from trinity.protocol.eth.peer import ETHPeerPool
from trinity.protocol.eth.sync import ETHHeaderChainSyncer
from trinity.sync.common.checkpoint import (
    Checkpoint,
)
from trinity.sync.common.chain import (
    BaseBlockImporter,
)
from trinity.sync.common.events import (
    CollectMissingAccount,
    CollectMissingBytecode,
    CollectMissingStorage,
    DoStatelessBlockImport,
    DoStatelessBlockPreview,
    MissingAccountCollected,
    MissingBytecodeCollected,
    MissingStorageCollected,
)
from trinity.sync.common.headers import (
    HeaderSyncerAPI,
    ManualHeaderSyncer,
)
from trinity.sync.common.strategies import (
    FromCheckpointLaunchStrategy,
    FromGenesisLaunchStrategy,
    SyncLaunchStrategyAPI,
)
from trinity.sync.full.chain import (
    FastChainBodySyncer,
    RegularChainBodySyncer,
)
from trinity.sync.full.constants import (
    HEADER_QUEUE_SIZE_TARGET,
)
from trinity.sync.beam.state import (
    BeamDownloader,
)
from trinity._utils.logging import HasExtendedDebugLogger
from trinity._utils.timer import Timer

STATS_DISPLAY_PERIOD = 10


class BeamSyncer(BaseService):
    """
    Organizes several moving parts to coordinate beam sync. Roughly:

        - Sync *only* headers up until you have caught up with a peer, ie~ the checkpoint
        - Launch a service responsible for serving event bus requests for missing state data
        - When you catch up with a peer, start downloading transactions needed to execute a block
        - At the checkpoint, switch to full block imports, with a custom importer

    This syncer relies on a seperately orchestrated beam sync plugin, which:

        - listens for DoStatelessBlockImport events
        - emits events when data is missing, like CollectMissingAccount
        - emits StatelessBlockImportDone when the block import is completed in the DB

    There is an option, currently only used for testing, to force beam sync at a particular
    block number (rather than trigger it when catching up with a peer).
    """
    def __init__(
            self,
            chain: AsyncChainAPI,
            db: BaseAtomicDB,
            chain_db: BaseAsyncChainDB,
            peer_pool: ETHPeerPool,
            event_bus: EndpointAPI,
            checkpoint: Checkpoint = None,
            force_beam_block_number: int = None,
            token: CancelToken = None) -> None:
        super().__init__(token=token)

        if checkpoint is None:
            self._launch_strategy: SyncLaunchStrategyAPI = FromGenesisLaunchStrategy(
                chain_db,
                chain
            )
        else:
            self._launch_strategy = FromCheckpointLaunchStrategy(
                chain_db,
                chain,
                checkpoint,
                peer_pool,
            )

        self._header_syncer = ETHHeaderChainSyncer(
            chain,
            chain_db,
            peer_pool,
            self._launch_strategy,
            self.cancel_token
        )
        self._header_persister = HeaderOnlyPersist(
            self._header_syncer,
            chain_db,
            force_beam_block_number,
            self._launch_strategy,
            self.cancel_token,
        )
        self._state_downloader = BeamDownloader(db, peer_pool, event_bus, self.cancel_token)
        self._data_hunter = MissingDataEventHandler(
            self._state_downloader,
            event_bus,
            token=self.cancel_token,
        )

        self._block_importer = BeamBlockImporter(
            chain,
            db,
            self._state_downloader,
            event_bus,
            self.cancel_token,
        )
        self._checkpoint_header_syncer = HeaderCheckpointSyncer(self._header_syncer)
        self._body_syncer = RegularChainBodySyncer(
            chain,
            chain_db,
            peer_pool,
            self._checkpoint_header_syncer,
            self._block_importer,
            self.cancel_token,
        )

        self._manual_header_syncer = ManualHeaderSyncer()
        self._fast_syncer = RigorousFastChainBodySyncer(
            chain,
            chain_db,
            peer_pool,
            self._manual_header_syncer,
            self.cancel_token,
        )

        self._chain = chain

    async def _run(self) -> None:

        try:
            await self.wait(self._launch_strategy.fulfill_prerequisites())
        except TimeoutError:
            self.logger.error(
                "Timed out while trying to fulfill prerequisites of"
                f"sync launch strategy: {self._launch_strategy}"
            )
            await self.cancel()

        self.run_daemon(self._header_syncer)

        # Kick off the body syncer early (it hangs on the checkpoint header syncer anyway)
        # It needs to start early because we want to "re-run" the header at the tip,
        # which it gets grumpy about. (it doesn't want to receive the canonical header tip
        # as a header to process)
        self.run_daemon(self._body_syncer)

        # Launch the state syncer endpoint early
        self.run_daemon(self._data_hunter)

        # Only persist headers at start
        await self.wait(self._header_persister.run())
        # When header store exits, we have caught up

        # We want to trigger beam sync on the last block received,
        # not wait for the next one to be broadcast
        final_headers = self._header_persister.get_final_headers()

        # First, download block bodies for previous 6 blocks, for validation
        await self._download_blocks(final_headers[0])

        # Now let the beam sync importer kick in
        self._checkpoint_header_syncer.set_checkpoint_headers(final_headers)

        # TODO wait until first header with a body comes in?...
        # Start state downloader service
        self.run_daemon(self._state_downloader)

        # run sync until cancelled
        await self.cancellation()

    async def _download_blocks(self, before_header: BlockHeader) -> None:
        """
        When importing a block, we need to validate uncles against the previous
        six blocks, so download those bodies and persist them to the database.
        """
        # We need MAX_UNCLE_DEPTH + 1 headers to check during uncle validation
        # We need to request one more header, to set the starting tip
        parents_needed = MAX_UNCLE_DEPTH + 2

        self.logger.info(
            "Downloading %d block bodies for uncle validation, before %s",
            parents_needed,
            before_header,
        )

        # select the recent ancestors to sync block bodies for
        parent_headers = tuple(reversed([
            header async for header
            in self._get_ancestors(parents_needed, header=before_header)
        ]))

        # identify starting tip and headers with possible uncle conflicts for validation
        if len(parent_headers) < parents_needed:
            self.logger.info(
                "Collecting %d blocks to genesis for uncle validation",
                len(parent_headers),
            )
            sync_from_tip = await self._chain.coro_get_canonical_block_by_number(BlockNumber(0))
            uncle_conflict_headers = parent_headers
        else:
            sync_from_tip = parent_headers[0]
            uncle_conflict_headers = parent_headers[1:]

        # check if we already have the blocks for the uncle conflict headers
        if await self._all_verification_bodies_present(uncle_conflict_headers):
            self.logger.debug("All needed block bodies are already available")
        else:
            # tell the header syncer to emit those headers
            self._manual_header_syncer.emit(uncle_conflict_headers)

            # tell the fast syncer which tip to start from
            self._fast_syncer.set_starting_tip(sync_from_tip)

            # run the fast syncer (which downloads block bodies and then exits)
            self.logger.info("Getting recent block data for uncle validation")
            await self._fast_syncer.run()

        # When this completes, we have all the uncles needed to validate
        self.logger.info("Have all data needed for Beam validation, continuing...")

    async def _get_ancestors(self, limit: int, header: BlockHeader) -> AsyncIterator[BlockHeader]:
        """
        Return `limit` number of ancestor headers from the specified header.
        """
        headers_returned = 0
        while header.parent_hash != GENESIS_PARENT_HASH and headers_returned < limit:
            parent = await self._chain.coro_get_block_header_by_hash(header.parent_hash)
            yield parent
            headers_returned += 1
            header = parent

    async def _all_verification_bodies_present(
            self,
            headers_with_potential_conflicts: Iterable[BlockHeader]) -> bool:

        for header in headers_with_potential_conflicts:
            if not await self._fast_syncer._should_skip_header(header):
                return False
        return True


class RigorousFastChainBodySyncer(FastChainBodySyncer):
    """
    Very much like the regular FastChainBodySyncer, but does a more robust
    check about whether we should skip syncing a header's body. We explicitly
    check if the body has been downloaded, instead of just trusting that if
    the header is present than the body must be. This is helpful, because
    the previous syncer is a header-only syncer.
    """
    _starting_tip: BlockHeader = None

    async def _should_skip_header(self, header: BlockHeader) -> bool:
        """
        Should we skip trying to import this header?
        Return True if the syncing of header appears to be complete.

        Only skip the header if we've definitely got the body downloaded
        """
        if not await self.db.coro_header_exists(header.hash):
            return False
        try:
            await self.chain.coro_get_block_by_header(header)
        except (HeaderNotFound, KeyError):
            # TODO unify these exceptions in py-evm, returning BlockBodyNotFound instead
            return False
        else:
            return True

    async def _sync_from(self) -> BlockHeader:
        """
        Typically, the FastChainBodySyncer always starts syncing from the tip of the chain,
        but we actually want to sync from *behind* the tip, so we manually set the sync-from
        target.
        """
        if self._starting_tip is None:
            raise ValidationError("Must set a previous tip before rigorous-fast-syncing")
        else:
            return self._starting_tip

    def set_starting_tip(self, header: BlockHeader) -> None:
        """
        Explicitly set the sync-from target, to use instead of the canonical head.
        """
        self._starting_tip = header


class HeaderCheckpointSyncer(HeaderSyncerAPI, HasExtendedDebugLogger):
    """
    Wraps a "real" header syncer, and drops headers on the floor, until triggered
    at a "checkpoint".

    Return the headers at the cehckpoint, and then pass through all the headers
    subsequently found by the header syncer.

    Can be used by a body syncer to pause syncing until a header checkpoint is reached.
    """
    def __init__(self, passthrough: HeaderSyncerAPI) -> None:
        self._real_syncer = passthrough
        self._at_checkpoint = asyncio.Event()
        self._checkpoint_headers: Tuple[BlockHeader, ...] = None

    def set_checkpoint_headers(self, headers: Tuple[BlockHeader, ...]) -> None:
        """
        Identify the given headers as checkpoint headers. These will be returned first.

        Immediately after these checkpoint headers are returned, start consuming and
        passing through all headers from the wrapped header syncer.
        """
        self._checkpoint_headers = headers
        self._at_checkpoint.set()

    async def new_sync_headers(
            self,
            max_batch_size: int = None) -> AsyncIterator[Tuple[BlockHeader, ...]]:
        await self._at_checkpoint.wait()

        self.logger.info("Choosing %s as checkpoint headers to sync from", self._checkpoint_headers)
        yield self._checkpoint_headers

        async for headers in self._real_syncer.new_sync_headers(max_batch_size):
            yield headers

    def get_target_header_hash(self) -> Hash32:
        return self._real_syncer.get_target_header_hash()


class HeaderOnlyPersist(BaseService):
    """
    Store all headers returned by the header syncer, until the target is reached, then exit.
    """
    def __init__(self,
                 header_syncer: ETHHeaderChainSyncer,
                 db: BaseAsyncHeaderDB,
                 force_end_block_number: int = None,
                 launch_strategy: SyncLaunchStrategyAPI = None,
                 token: CancelToken = None) -> None:
        super().__init__(token=token)
        self._db = db
        self._header_syncer = header_syncer
        self._final_headers: Tuple[BlockHeader, ...] = None
        self._force_end_block_number = force_end_block_number
        self._launch_strategy = launch_strategy

    async def _run(self) -> None:
        self.run_daemon_task(self._persist_headers())
        # run sync until cancelled
        await self.cancellation()

    async def _persist_header_chain(self, headers: Tuple[BlockHeader, ...]) -> None:
        await self.wait(
            self._db.coro_persist_header_chain(
                headers,
                self._launch_strategy.get_genesis_parent_hash(),
            )
        )

    async def _persist_headers(self) -> None:
        async for headers in self._header_syncer.new_sync_headers(HEADER_QUEUE_SIZE_TARGET):
            timer = Timer()

            exited = await self._exit_if_checkpoint(headers)
            if exited:
                break

            await self._persist_header_chain(headers)

            head = await self.wait(self._db.coro_get_canonical_head())

            self.logger.info(
                "Imported %d headers in %0.2f seconds, new head: %s",
                len(headers),
                timer.elapsed,
                head,
            )

    async def _exit_if_checkpoint(self, headers: Tuple[BlockHeader, ...]) -> bool:
        """
        Determine if the supplied headers have reached the end of headers-only persist.
        This might be in the form of a forced checkpoint, or because we caught up to
        our peer's target checkpoint.

        In the case that we have reached the checkpoint:

            - trigger service exit
            - persist the headers before the checkpoint
            - save the headers that triggered the checkpoint (retrievable via get_final_headers)

        :return: whether we have reached the checkpoint
        """
        ending_header_search = [
            header for header in headers if header.block_number == self._force_end_block_number
        ]

        if ending_header_search:
            # Force an early exit to beam sync
            self.logger.info(
                "Forced the beginning of Beam Sync at %s",
                ending_header_search[0],
            )
            persist_headers = tuple(
                h for h in headers
                if h.block_number < self._force_end_block_number
            )
            final_headers = tuple(
                h for h in headers
                if h.block_number >= self._force_end_block_number
            )
        else:
            target_hash = self._header_syncer.get_target_header_hash()
            if target_hash in (header.hash for header in headers):
                self.logger.info(
                    "Caught up to skeleton peer. Switching to beam mode at %s",
                    headers[-1],
                )

                # We have reached the header syncer's target
                # Only sync against the most recent header
                persist_headers, final_headers = headers[:-1], headers[-1:]
            else:
                # We have not reached the header syncer's target, continue normally
                return False

        await self._persist_header_chain(persist_headers)

        self._final_headers = final_headers
        self.cancel_nowait()
        return True

    def get_final_headers(self) -> Tuple[BlockHeader, ...]:
        """
        Which header(s) triggered the checkpoint to switch out of header-only persist state.

        :raise ValidationError: if the syncer has not reached the checkpoint yet
        """
        if self._final_headers is None:
            raise ValidationError("Must not try to access final headers before it has been set")
        else:
            return self._final_headers


class BeamBlockImporter(BaseBlockImporter, BaseService):
    """
    Block Importer that emits DoStatelessBlockImport and waits on the event bus for a
    StatelessBlockImportDone to show that the import is complete.

    It independently runs other state preloads, like the accounts for the
    block transactions.
    """
    def __init__(
            self,
            chain: AsyncChainAPI,
            db: DatabaseAPI,
            state_getter: BeamDownloader,
            event_bus: EndpointAPI,
            token: CancelToken=None) -> None:
        super().__init__(token=token)

        self._chain = chain
        self._db = db
        self._state_downloader = state_getter

        self._blocks_imported = 0
        self._preloaded_account_state = 0
        self._preloaded_previewed_account_state = 0
        self._preloaded_account_time: float = 0
        self._preloaded_previewed_account_time: float = 0
        self._import_time: float = 0

        self._event_bus = event_bus
        # TODO: implement speculative execution, but at the txn level instead of block level

    async def import_block(
            self,
            block: BaseBlock) -> Tuple[BaseBlock, Tuple[BaseBlock, ...], Tuple[BaseBlock, ...]]:
        self.logger.info("Beam importing %s (%d txns) ...", block.header, len(block.transactions))

        parent_header = await self._chain.coro_get_block_header_by_hash(block.header.parent_hash)
        new_account_nodes, collection_time = await self._load_address_state(
            block.header,
            parent_header.state_root,
            block.transactions,
        )
        self._preloaded_account_state += new_account_nodes
        self._preloaded_account_time += collection_time

        import_timer = Timer()
        import_done = await self._event_bus.request(DoStatelessBlockImport(block))
        self._import_time += import_timer.elapsed

        if not import_done.completed:
            raise ValidationError("Block import was cancelled, probably a shutdown")
        if import_done.exception:
            raise ValidationError("Block import failed") from import_done.exception
        if import_done.block.hash != block.hash:
            raise ValidationError(f"Requsted {block} to be imported, but ran {import_done.block}")
        self._blocks_imported += 1
        self._log_stats()
        return import_done.result

    async def preview_transactions(
            self,
            header: BlockHeader,
            transactions: Tuple[BaseTransaction, ...],
            parent_state_root: Hash32,
            lagging: bool = True) -> None:

        self.run_task(self._preview_address_load(header, parent_state_root, transactions))

        # This is a hack, so that preview executions can load ancestor block-hashes
        self._db[header.hash] = rlp.encode(header)

        # Always broadcast, to start previewing transactions that are further ahead in the block
        old_state_header = header.copy(state_root=parent_state_root)
        self._event_bus.broadcast_nowait(
            DoStatelessBlockPreview(old_state_header, transactions)
        )

    async def _preview_address_load(
            self,
            header: BlockHeader,
            parent_state_root: Hash32,
            transactions: Tuple[BaseTransaction, ...]) -> None:
        """
        Get account state for transaction addresses on a block being previewed in parallel.
        """
        new_account_nodes, collection_time = await self._load_address_state(
            header,
            parent_state_root,
            transactions,
            urgent=False,
        )
        self._preloaded_previewed_account_state += new_account_nodes
        self._preloaded_previewed_account_time += collection_time

    async def _load_address_state(
            self,
            header: BlockHeader,
            parent_state_root: Hash32,
            transactions: Tuple[BaseTransaction, ...],
            urgent: bool=True) -> Tuple[int, float]:
        """
        Load all state needed to read transaction account status.
        """

        address_timer = Timer()
        num_accounts, new_account_nodes = await self._request_address_nodes(
            header,
            parent_state_root,
            transactions,
            urgent,
        )
        collection_time = address_timer.elapsed

        self.logger.debug(
            "Previewed %s state for %d addresses in %.2fs; got %d trie nodes; urgent? %r",
            header,
            num_accounts,
            collection_time,
            new_account_nodes,
            urgent,
        )

        return new_account_nodes, collection_time

    def _log_stats(self) -> None:
        stats = {
            "preload_nodes": self._preloaded_account_state,
            "preload_time": self._preloaded_account_time,
            "preload_preview_nodes": self._preloaded_previewed_account_state,
            "preload_preview_time": self._preloaded_previewed_account_time,
            "import_time": self._import_time,
        }
        if self._blocks_imported:
            mean_stats = {key: val / self._blocks_imported for key, val in stats.items()}
        else:
            mean_stats = None
        self.logger.debug(
            "Beam Download of %d blocks: "
            "%r, block_average: %r",
            self._blocks_imported,
            stats,
            mean_stats,
        )

    async def _request_address_nodes(
            self,
            header: BlockHeader,
            parent_state_root: Hash32,
            transactions: Tuple[BaseTransaction, ...],
            urgent: bool=True) -> Tuple[int, int]:
        """
        Request any missing trie nodes needed to read account state for the given transactions.

        :param urgent: are these addresses needed immediately? If False, they should they queue
            up behind the urgent trie nodes.
        """
        senders = [transaction.sender for transaction in transactions]
        recipients = [transaction.to for transaction in transactions if transaction.to]
        addresses = set(senders + recipients + [header.coinbase])
        collected_nodes = await self._state_downloader.download_accounts(
            addresses,
            parent_state_root,
            urgent=urgent,
        )
        return len(addresses), collected_nodes

    async def _run(self) -> None:
        await self.cancellation()


class MissingDataEventHandler(BaseService):
    """
    Listen to event bus requests for missing account, storage and bytecode.
    Request the data on demand, and reply when it is available.
    """

    def __init__(
            self,
            state_downloader: BeamDownloader,
            event_bus: EndpointAPI,
            token: CancelToken=None) -> None:
        super().__init__(token=token)
        self._state_downloader = state_downloader
        self._event_bus = event_bus

    async def _run(self) -> None:
        await self._launch_server()
        await self.cancellation()

    async def _launch_server(self) -> None:
        self.run_daemon_task(self._provide_missing_account_tries())
        self.run_daemon_task(self._provide_missing_bytecode())
        self.run_daemon_task(self._provide_missing_storage())

    async def _provide_missing_account_tries(self) -> None:
        async for event in self.wait_iter(self._event_bus.stream(CollectMissingAccount)):
            self.run_task(self._serve_account(event))

    async def _provide_missing_bytecode(self) -> None:
        async for event in self.wait_iter(self._event_bus.stream(CollectMissingBytecode)):
            self.run_task(self._serve_bytecode(event))

    async def _provide_missing_storage(self) -> None:
        async for event in self.wait_iter(self._event_bus.stream(CollectMissingStorage)):
            self.run_task(self._serve_storage(event))

    async def _serve_account(self, event: CollectMissingAccount) -> None:
        _, num_nodes_collected = await self._state_downloader.download_account(
            event.address_hash,
            event.state_root_hash,
            event.urgent,
        )
        bonus_node = await self._state_downloader.ensure_nodes_present(
            {event.missing_node_hash},
            event.urgent,
        )
        await self._event_bus.broadcast(
            MissingAccountCollected(num_nodes_collected + bonus_node),
            event.broadcast_config(),
        )

    async def _serve_bytecode(self, event: CollectMissingBytecode) -> None:
        await self._state_downloader.ensure_nodes_present({event.bytecode_hash}, event.urgent)
        await self._event_bus.broadcast(MissingBytecodeCollected(), event.broadcast_config())

    async def _serve_storage(self, event: CollectMissingStorage) -> None:
        num_nodes_collected = await self._state_downloader.download_storage(
            event.storage_key,
            event.storage_root_hash,
            event.account_address,
            event.urgent,
        )
        bonus_node = await self._state_downloader.ensure_nodes_present(
            {event.missing_node_hash},
            event.urgent,
        )
        await self._event_bus.broadcast(
            MissingStorageCollected(num_nodes_collected + bonus_node),
            event.broadcast_config(),
        )
