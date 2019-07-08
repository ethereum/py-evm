import asyncio
from typing import (
    AsyncIterator,
    Iterable,
    Tuple,
)

from cancel_token import CancelToken
from eth.constants import GENESIS_PARENT_HASH, MAX_UNCLE_DEPTH
from eth.exceptions import (
    HeaderNotFound,
)
from eth.rlp.blocks import BaseBlock
from eth.rlp.headers import BlockHeader
from eth_typing import (
    Hash32,
    BlockNumber,
)
from eth_utils import (
    ValidationError,
)

from p2p.service import BaseService

from trinity.chains.base import BaseAsyncChain
from trinity.db.base import BaseAsyncDB
from trinity.db.eth1.chain import BaseAsyncChainDB
from trinity.db.eth1.header import BaseAsyncHeaderDB
from trinity.endpoint import TrinityEventBusEndpoint
from trinity.protocol.eth.peer import ETHPeerPool
from trinity.protocol.eth.sync import ETHHeaderChainSyncer
from trinity.sync.common.chain import (
    BaseBlockImporter,
)
from trinity.sync.common.events import (
    CollectMissingAccount,
    CollectMissingBytecode,
    CollectMissingStorage,
    DoStatelessBlockImport,
    MissingAccountCollected,
    MissingBytecodeCollected,
    MissingStorageCollected,
)
from trinity.sync.common.headers import (
    HeaderSyncerAPI,
    ManualHeaderSyncer,
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
            chain: BaseAsyncChain,
            db: BaseAsyncDB,
            chain_db: BaseAsyncChainDB,
            peer_pool: ETHPeerPool,
            event_bus: TrinityEventBusEndpoint,
            force_beam_block_number: int = None,
            token: CancelToken = None) -> None:
        super().__init__(token=token)

        self._header_syncer = ETHHeaderChainSyncer(chain, chain_db, peer_pool, self.cancel_token)
        self._header_persister = HeaderOnlyPersist(
            self._header_syncer,
            chain_db,
            force_beam_block_number,
            self.cancel_token,
        )
        self._state_downloader = BeamDownloader(db, peer_pool, event_bus, self.cancel_token)
        self._data_hunter = MissingDataEventHandler(
            self._state_downloader,
            event_bus,
            token=self.cancel_token,
        )

        self._block_importer = BeamBlockImporter(chain, self._state_downloader, event_bus)
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
        self.logger.info(
            "Downloading %d block bodies for uncle validation, before %s",
            MAX_UNCLE_DEPTH,
            before_header,
        )

        # select the recent ancestors to sync block bodies for
        parent_headers = tuple(reversed([
            header async for header
            in self._get_ancestors(MAX_UNCLE_DEPTH + 1, header=before_header)
        ]))

        # identify starting tip and headers with possible uncle conflicts for validation
        if len(parent_headers) <= MAX_UNCLE_DEPTH:
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
                 token: CancelToken = None) -> None:
        super().__init__(token=token)
        self._db = db
        self._header_syncer = header_syncer
        self._final_headers: Tuple[BlockHeader, ...] = None
        self._force_end_block_number = force_end_block_number

    async def _run(self) -> None:
        self.run_daemon_task(self._persist_headers())
        # run sync until cancelled
        await self.cancellation()

    async def _persist_headers(self) -> None:
        async for headers in self._header_syncer.new_sync_headers(HEADER_QUEUE_SIZE_TARGET):
            timer = Timer()

            exited = await self._exit_if_checkpoint(headers)
            if exited:
                break

            await self.wait(self._db.coro_persist_header_chain(headers))

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

        await self.wait(self._db.coro_persist_header_chain(persist_headers))

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


class BeamBlockImporter(BaseBlockImporter, HasExtendedDebugLogger):
    """
    Block Importer that emits DoStatelessBlockImport and waits on the event bus for a
    StatelessBlockImportDone to show that the import is complete.

    It independently runs other state preloads, like the accounts for the
    block transactions.
    """
    def __init__(
            self,
            chain: BaseAsyncChain,
            state_getter: BeamDownloader,
            event_bus: TrinityEventBusEndpoint) -> None:
        self._chain = chain
        self._state_downloader = state_getter

        self._blocks_imported = 0
        self._preloaded_account_state = 0

        self._event_bus = event_bus
        # TODO: implement speculative execution, but at the txn level instead of block level

    async def import_block(
            self,
            block: BaseBlock) -> Tuple[BaseBlock, Tuple[BaseBlock, ...], Tuple[BaseBlock, ...]]:
        self.logger.info("Beam importing %s (%d txns) ...", block.header, len(block.transactions))

        new_account_nodes = await self._pre_check_addresses(block)
        self._preloaded_account_state += new_account_nodes

        import_done = await self._event_bus.request(DoStatelessBlockImport(block))
        if not import_done.completed:
            raise ValidationError("Block import was cancelled, probably a shutdown")
        if import_done.exception:
            raise ValidationError("Block import failed") from import_done.exception
        if import_done.block.hash != block.hash:
            raise ValidationError(f"Requsted {block} to be imported, but ran {import_done.block}")
        self._blocks_imported += 1
        self._log_stats()
        return import_done.result

    def _log_stats(self) -> None:
        stats = {"account_preload": self._preloaded_account_state}
        if self._blocks_imported:
            mean_stats = {key: val / self._blocks_imported for key, val in stats.items()}
        else:
            mean_stats = None
        self.logger.info(
            "Beam Download: "
            "%r, block_average: %r",
            stats,
            mean_stats,
        )

    async def _pre_check_addresses(self, block: BaseBlock) -> int:
        senders = [transaction.sender for transaction in block.transactions]
        recipients = [transaction.to for transaction in block.transactions if transaction.to]
        addresses = set(senders + recipients)
        parent_header = await self._chain.coro_get_block_header_by_hash(block.header.parent_hash)
        state_root_hash = parent_header.state_root
        return await self._state_downloader.download_accounts(addresses, state_root_hash)


class MissingDataEventHandler(BaseService):
    """
    Listen to event bus requests for missing account, storage and bytecode.
    Request the data on demand, and reply when it is available.
    """

    def __init__(
            self,
            state_downloader: BeamDownloader,
            event_bus: TrinityEventBusEndpoint,
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
            await self._state_downloader.ensure_node_present(event.missing_node_hash)
            await self._state_downloader.download_account(event.address_hash, event.state_root_hash)
            await self._event_bus.broadcast(MissingAccountCollected(), event.broadcast_config())

    async def _provide_missing_bytecode(self) -> None:
        async for event in self.wait_iter(self._event_bus.stream(CollectMissingBytecode)):
            await self._state_downloader.ensure_node_present(event.bytecode_hash)
            await self._event_bus.broadcast(MissingBytecodeCollected(), event.broadcast_config())

    async def _provide_missing_storage(self) -> None:
        async for event in self.wait_iter(self._event_bus.stream(CollectMissingStorage)):
            await self._state_downloader.ensure_node_present(event.missing_node_hash)
            await self._state_downloader.download_storage(
                event.storage_key,
                event.storage_root_hash,
                event.account_address,
            )
            await self._event_bus.broadcast(MissingStorageCollected(), event.broadcast_config())
