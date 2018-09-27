import asyncio
from asyncio import (
    PriorityQueue,
)
from concurrent.futures import CancelledError
import enum
from functools import (
    partial,
)
from operator import attrgetter
from typing import (
    Any,
    Dict,
    List,
    Set,
    Tuple,
    Type,
    Union,
    cast,
)

from cancel_token import CancelToken, OperationCancelled
from eth_typing import Hash32
from eth_utils import (
    ValidationError,
)
from eth_utils.toolz import (
    concat,
    first,
    groupby,
    merge,
    valfilter,
)

from eth.chains import AsyncChain
from eth.constants import (
    BLANK_ROOT_HASH,
    EMPTY_UNCLE_HASH,
)
from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt
from eth.rlp.transactions import BaseTransaction

from p2p import protocol
from p2p.p2p_proto import DisconnectReason
from p2p.exceptions import BaseP2PError, PeerConnectionLost
from p2p.peer import BasePeer
from p2p.protocol import Command

from trinity.db.chain import AsyncChainDB
from trinity.db.header import AsyncHeaderDB
from trinity.protocol.eth import commands
from trinity.protocol.eth.constants import (
    MAX_BODIES_FETCH,
    MAX_RECEIPTS_FETCH,
    MAX_STATE_FETCH,
)
from trinity.protocol.eth.peer import ETHPeer, ETHPeerPool
from trinity.protocol.eth.requests import HeaderRequest
from trinity.protocol.les.peer import LESPeer
from trinity.rlp.block_body import BlockBody
from trinity.sync.common.chain import BaseHeaderChainSyncer
from trinity.utils.datastructures import (
    DuplicateTasks,
    SortableTask,
    MissingDependency,
    OrderedTaskPreparation,
    TaskQueue,
)
from trinity.utils.timer import Timer

HeaderRequestingPeer = Union[LESPeer, ETHPeer]
# (ReceiptBundle, (Receipt, (root_hash, receipt_trie_data))
ReceiptBundle = Tuple[Tuple[Receipt, ...], Tuple[Hash32, Dict[Hash32, bytes]]]
# (BlockBody, (txn_root, txn_trie_data), uncles_hash)
BlockBodyBundle = Tuple[
    BlockBody,
    Tuple[Hash32, Dict[Hash32, bytes]],
    Hash32,
]

# How big should the pending request queue get, as a multiple of the largest request size
REQUEST_BUFFER_MULTIPLIER = 8


class WaitingPeers:
    """
    Peers waiting to perform some action. When getting a peer from this queue,
    prefer the peer with the best throughput for the given command.
    """
    _waiting_peers: 'PriorityQueue[SortableTask[ETHPeer]]'

    def __init__(self, response_command_type: Type[Command]) -> None:
        self._waiting_peers = PriorityQueue()
        self._response_command_type = response_command_type
        self._peer_wrapper = SortableTask.orderable_by_func(self._ranked_peer)

    def _ranked_peer(self, peer: ETHPeer) -> float:
        relevant_throughputs = [
            exchange.tracker.items_per_second_ema.value
            for exchange in peer.requests
            if exchange.response_cmd_type == self._response_command_type
        ]

        if len(relevant_throughputs) == 0:
            raise ValidationError(
                f"Could not find any exchanges on {peer} "
                f"with response {self._response_command_type!r}"
            )

        avg_throughput = sum(relevant_throughputs) / len(relevant_throughputs)

        # high throughput peers should pop out of the queue first, so ranked as negative
        return -1 * avg_throughput

    def put_nowait(self, peer: ETHPeer) -> None:
        self._waiting_peers.put_nowait(self._peer_wrapper(peer))

    async def get_fastest(self) -> ETHPeer:
        wrapped_peer = await self._waiting_peers.get()
        peer = wrapped_peer.original

        # make sure the peer has not gone offline while waiting in the queue
        while not peer.is_operational:
            # if so, look for the next best peer
            wrapped_peer = await self._waiting_peers.get()
            peer = wrapped_peer.original

        return peer


class BaseBodyChainSyncer(BaseHeaderChainSyncer):

    NO_PEER_RETRY_PAUSE = 5.0
    "If no peers are available for downloading the chain data, retry after this many seconds"

    EMPTY_PEER_RESPONSE_PENALTY = 3.0
    "After a peer returns zero results, it will wait this many seconds before retrying"

    db: AsyncChainDB

    subscription_msg_types: Set[Type[Command]] = {
        commands.NewBlock,
        commands.GetBlockHeaders,
        commands.GetBlockBodies,
        commands.GetReceipts,
        commands.GetNodeData,
        # TODO: all of the following are here to quiet warning logging output
        # until the messages are properly handled.
        commands.Transactions,
        commands.NewBlockHashes,
    }
    _pending_bodies: Dict[BlockHeader, BlockBody]

    def __init__(self,
                 chain: AsyncChain,
                 db: AsyncHeaderDB,
                 peer_pool: ETHPeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(chain, db, peer_pool, token)
        self._pending_bodies = {}

        # queue up any idle peers, in order of how fast they return block bodies
        self._body_peers = WaitingPeers(commands.BlockBodies)

        # Track incomplete block body download tasks
        # - arbitrarily allow several requests-worth of headers queued up
        # - try to get bodies from lower block numbers first
        buffer_size = MAX_BODIES_FETCH * REQUEST_BUFFER_MULTIPLIER
        self._block_body_tasks = TaskQueue(buffer_size, attrgetter('block_number'))

    async def _assign_body_download_to_peers(self) -> None:
        """
        Loop indefinitely, assigning idle peers to download any block bodies needed for syncing.
        """
        while self.is_operational:
            # from all the peers that are not currently downloading block bodies, get the fastest
            peer = await self.wait(self._body_peers.get_fastest())

            # get headers for bodies that we need to download, preferring lowest block number
            batch_id, headers = await self.wait(self._block_body_tasks.get(MAX_BODIES_FETCH))

            # schedule the body download and move on
            peer.run_task(self._run_body_download_batch(peer, batch_id, headers))

    async def _block_body_bundle_processing(self, bundles: Tuple[BlockBodyBundle, ...]) -> None:
        """
        By default, no body bundle processing is needed.

        Subclasses may choose to do some post-processing. Notably, fast sync immediately saves
        block body bundles to the database.
        """
        pass

    async def _run_body_download_batch(
            self,
            peer: ETHPeer,
            batch_id: int,
            all_headers: Tuple[BlockHeader, ...]) -> None:
        """
        Given a single batch retrieved from self._block_body_tasks, get as many of the block bodies
        as possible, and mark them as complete.
        """

        non_trivial_headers = tuple(header for header in all_headers if not _is_body_empty(header))
        trivial_headers = tuple(header for header in all_headers if _is_body_empty(header))

        if trivial_headers:
            self.logger.trace(
                "Found %d/%d trivial block bodies, skipping those requests",
                len(trivial_headers),
                len(all_headers),
            )

        # even if trivial_headers is (), assign it so the finally block can run, in case of error
        completed_headers = trivial_headers

        try:
            if non_trivial_headers:
                bundles, received_headers = await peer.wait(
                    self._get_block_bodies(peer, non_trivial_headers)
                )
                await self._block_body_bundle_processing(bundles)
                completed_headers = trivial_headers + received_headers

        except BaseP2PError as exc:
            self.logger.info("Unexpected p2p perror while downloading body from peer: %s", exc)
            self.logger.debug("Problem downloading body from peer, dropping...", exc_info=True)
        else:
            if len(non_trivial_headers) == 0:
                # peer had nothing to do, so have it get back in line for processing
                self._body_peers.put_nowait(peer)
            elif len(completed_headers) > 0:
                # peer completed with at least 1 result, so have it get back in line for processing
                self._body_peers.put_nowait(peer)
            else:
                # peer returned no results, wait a while before trying again
                delay = self.EMPTY_PEER_RESPONSE_PENALTY
                self.logger.debug("Pausing %s for %.1fs, for sending 0 block bodies", peer, delay)
                loop = self.get_event_loop()
                loop.call_later(delay, partial(self._body_peers.put_nowait, peer))
        finally:
            self._mark_body_download_complete(batch_id, completed_headers)

    def _mark_body_download_complete(
            self,
            batch_id: int,
            completed_headers: Tuple[BlockHeader, ...]) -> None:
        self._block_body_tasks.complete(batch_id, completed_headers)

    async def _get_block_bodies(
            self,
            peer: ETHPeer,
            headers: Tuple[BlockHeader, ...],
    ) -> Tuple[Tuple[BlockBodyBundle, ...], Tuple[BlockHeader, ...]]:
        """
        Request and return block bodies, pairing them with the associated headers.
        Store the bodies for later use, during block import (or persist).

        Note the difference from _request_block_bodies, which only issues the request,
        and doesn't pair the results with the associated block headers that were successfully
        delivered.
        """
        block_body_bundles = await self.wait(self._request_block_bodies(peer, headers))

        if len(block_body_bundles) == 0:
            self.logger.debug(
                "Got block bodies for 0/%d headers from %s, from %r..%r",
                len(headers),
                peer,
                headers[0],
                headers[-1],
            )
            return tuple(), tuple()

        bodies_by_root = {
            (transaction_root, uncles_hash): block_body
            for block_body, (transaction_root, _), uncles_hash
            in block_body_bundles
        }

        header_roots = {header: (header.transaction_root, header.uncles_hash) for header in headers}

        completed_header_roots = valfilter(lambda root: root in bodies_by_root, header_roots)

        completed_headers = tuple(completed_header_roots.keys())

        # store bodies for later usage, during block import
        pending_bodies = {
            header: bodies_by_root[root]
            for header, root in completed_header_roots.items()
        }
        self._pending_bodies = merge(self._pending_bodies, pending_bodies)

        self.logger.debug(
            "Got block bodies for %d/%d headers from %s, from %r..%r",
            len(completed_header_roots),
            len(headers),
            peer,
            headers[0],
            headers[-1],
        )

        return block_body_bundles, completed_headers

    async def _request_block_bodies(
            self,
            peer: ETHPeer,
            batch: Tuple[BlockHeader, ...]) -> Tuple[BlockBodyBundle, ...]:
        """
        Requests the batch of block bodies from the given peer, returning the
        returned block bodies data, or an empty tuple on an error.
        """
        self.logger.debug("Requesting block bodies for %d headers from %s", len(batch), peer)
        try:
            block_body_bundles = await peer.requests.get_block_bodies(batch)
        except TimeoutError as err:
            self.logger.debug(
                "Timed out requesting block bodies for %d headers from %s", len(batch), peer,
            )
            return tuple()
        except CancelledError:
            self.logger.debug("Pending block bodies call to %r future cancelled", peer)
            return tuple()
        except OperationCancelled:
            self.logger.trace("Pending block bodies call to %r operation cancelled", peer)
            return tuple()
        except PeerConnectionLost:
            self.logger.debug("Peer went away, cancelling the block body request and moving on...")
            return tuple()
        except Exception:
            self.logger.exception("Unknown error when getting block bodies")
            raise

        return block_body_bundles

    async def _handle_msg(self, peer: HeaderRequestingPeer, cmd: protocol.Command,
                          msg: protocol._DecodedMsgType) -> None:
        peer = cast(ETHPeer, peer)

        # TODO: stop ignoring these once we have proper handling for these messages.
        ignored_commands = (commands.Transactions, commands.NewBlockHashes)

        if isinstance(cmd, ignored_commands):
            pass
        elif isinstance(cmd, commands.NewBlock):
            await self._handle_new_block(peer, cast(Dict[str, Any], msg))
        elif isinstance(cmd, commands.GetBlockHeaders):
            await self._handle_get_block_headers(peer, cast(Dict[str, Any], msg))
        elif isinstance(cmd, commands.GetBlockBodies):
            # Only serve up to MAX_BODIES_FETCH items in every request.
            block_hashes = cast(List[Hash32], msg)[:MAX_BODIES_FETCH]
            await self._handler.handle_get_block_bodies(peer, block_hashes)
        elif isinstance(cmd, commands.GetReceipts):
            # Only serve up to MAX_RECEIPTS_FETCH items in every request.
            block_hashes = cast(List[Hash32], msg)[:MAX_RECEIPTS_FETCH]
            await self._handler.handle_get_receipts(peer, block_hashes)
        elif isinstance(cmd, commands.GetNodeData):
            # Only serve up to MAX_STATE_FETCH items in every request.
            node_hashes = cast(List[Hash32], msg)[:MAX_STATE_FETCH]
            await self._handler.handle_get_node_data(peer, node_hashes)
        else:
            self.logger.debug("%s msg not handled yet, need to be implemented", cmd)

    async def _handle_new_block(self, peer: ETHPeer, msg: Dict[str, Any]) -> None:
        self._sync_requests.put_nowait(peer)

    async def _handle_get_block_headers(
            self,
            peer: ETHPeer,
            query: Dict[str, Any]) -> None:
        if not peer.is_operational:
            return
        self.logger.debug("Peer %s made header request: %s", peer, query)
        request = HeaderRequest(
            query['block_number_or_hash'],
            query['max_headers'],
            query['skip'],
            query['reverse'],
        )

        headers = await self._handler.lookup_headers(request)
        self.logger.trace("Replying to %s with %d headers", peer, len(headers))
        peer.sub_proto.send_block_headers(headers)


class BlockPersistPrereqs(enum.Enum):
    StoreBlockBodies = enum.auto()
    StoreReceipts = enum.auto()


class FastChainSyncer(BaseBodyChainSyncer):
    """
    Sync with the Ethereum network by fetching block headers/bodies and storing them in our DB.

    Here, the run() method returns as soon as we complete a sync with the peer that announced the
    highest TD, at which point we must run the StateDownloader to fetch the state for our chain
    head.
    """
    db: AsyncChainDB

    def __init__(self,
                 chain: AsyncChain,
                 db: AsyncHeaderDB,
                 peer_pool: ETHPeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(chain, db, peer_pool, token)

        # queue up any idle peers, in order of how fast they return receipts
        self._receipt_peers = WaitingPeers(commands.Receipts)

        # Track receipt download tasks
        # - arbitrarily allow several requests-worth of headers queued up
        # - try to get receipts from lower block numbers first
        buffer_size = MAX_RECEIPTS_FETCH * REQUEST_BUFFER_MULTIPLIER
        self._receipt_tasks = TaskQueue(buffer_size, attrgetter('block_number'))

        # track when both bodies and receipts are collected, so that blocks can be persisted
        self._block_persist_tracker = OrderedTaskPreparation(
            BlockPersistPrereqs,
            id_extractor=attrgetter('hash'),
            # make sure that a block is not persisted until the parent block is persisted
            dependency_extractor=attrgetter('parent_hash'),
        )

    async def _run(self) -> None:
        head = await self.wait(self.db.coro_get_canonical_head())
        self._block_persist_tracker.set_finished_dependency(head)
        self.run_daemon_task(self._launch_prerequisite_tasks())
        self.run_daemon_task(self._assign_receipt_download_to_peers())
        self.run_daemon_task(self._assign_body_download_to_peers())
        self.run_daemon_task(self._persist_ready_blocks())
        self.run_daemon_task(self._display_stats())
        await super()._run()

    def register_peer(self, peer: BasePeer) -> None:
        # when a new peer is added to the pool, add it to the idle peer lists
        super().register_peer(peer)
        peer = cast(ETHPeer, peer)
        self._body_peers.put_nowait(peer)
        self._receipt_peers.put_nowait(peer)

    async def _launch_prerequisite_tasks(self) -> None:
        """
        Watch for new headers to be added to the queue, and add the prerequisite
        tasks as they become available.
        """
        while self.is_operational:
            batch_id, headers = await self.wait(self.header_queue.get())

            try:
                self._block_persist_tracker.register_tasks(headers)
            except DuplicateTasks as exc:
                # Likely scenario: switched which peer downloads headers, and the new peer isn't
                # aware of some of the in-progress headers
                self.logger.debug("Duplicate headers during fast sync %r, skipping", exc.duplicates)
                duplicates = cast(Tuple[BlockHeader, ...], exc.duplicates)
                self.header_queue.complete(batch_id, duplicates)
                continue
            except MissingDependency:
                # The parent of this header is not registered as a dependency yet.
                # Some reasons this might happen, in rough descending order of likelihood:
                #   - a normal fork: the canonical head isn't the parent of the first header synced
                #   - a bug: the DB has inconsistent state, say saved headers but not block bodies
                #   - a bug: headers were queued out of order in header_queue

                # If the parent header doesn't exist yet, this is a legit bug instead of a fork,
                # let the HeaderNotFound exception bubble up
                parent_header = await self.wait(
                    self.db.coro_get_block_header_by_hash(headers[0].parent_hash)
                )

                # This appears to be a fork, since the parent header is persisted,
                self.logger.info(
                    "Fork found while starting fast sync. Canonical head was %s, but the next "
                    "header %s, has parent %s. Importing fork in case it's the longest chain.",
                    await self.db.coro_get_canonical_head(),
                    headers[0],
                    parent_header,
                )
                # Set first header's parent as finished
                self._block_persist_tracker.set_finished_dependency(parent_header)
                # Re-register the header tasks, which will now succeed
                self._block_persist_tracker.register_tasks(headers)

            # Sometimes duplicates are added to the queue, when switching from one sync to another.
            # We can simply ignore them.
            new_body_tasks = tuple(h for h in headers if h not in self._block_body_tasks)
            new_receipt_tasks = tuple(h for h in headers if h not in self._receipt_tasks)

            # if any one of the output queues gets full, hang until there is room
            await self.wait(asyncio.gather(
                self._block_body_tasks.add(new_body_tasks),
                self._receipt_tasks.add(new_receipt_tasks),
            ))
            self.header_queue.complete(batch_id, headers)

    async def _display_stats(self) -> None:
        last_head = await self.wait(self.db.coro_get_canonical_head())
        timer = Timer()

        while self.is_operational:
            await self.sleep(5)
            self.logger.debug(
                "(in progress, queued, max size) of headers, bodies, receipts: %r",
                [(q.num_in_progress(), len(q), q._maxsize) for q in (
                    self.header_queue,
                    self._block_body_tasks,
                    self._receipt_tasks,
                )],
            )

            head = await self.wait(self.db.coro_get_canonical_head())
            if head == last_head:
                continue
            else:
                block_num_change = head.block_number - last_head.block_number
                last_head = head

                self.logger.info(
                    "Advanced by %d blocks in %0.1f seconds, new head: #%d",
                    block_num_change, timer.pop_elapsed(), head.block_number)

    async def _persist_ready_blocks(self) -> None:
        """
        Persist blocks as soon as all their prerequisites are done: body and receipt downloads.
        Persisting must happen in order, so that the block's parent has already been persisted.

        Also, determine if fast sync with this peer should end, having reached (or surpassed)
        its target hash. If so, shut down this service.
        """
        while self.is_operational:
            # jhis tracker waits for all prerequisites to be complete, and returns headers in
            # order, so that each header's parent is already persisted.
            completed_headers = await self.wait(self._block_persist_tracker.ready_tasks())

            await self._persist_blocks(completed_headers)

            target_hash = self.get_target_header_hash()

            if target_hash in [header.hash for header in completed_headers]:
                # simply exit the service when reaching the target hash
                self.cancel_nowait()
                break

    async def _persist_blocks(self, headers: Tuple[BlockHeader, ...]) -> None:
        """
        Persist blocks for the given headers, directly to the database

        :param headers: headers for which block bodies and receipts have been downloaded
        """
        for header in headers:
            vm_class = self.chain.get_vm_class(header)
            block_class = vm_class.get_block_class()

            if _is_body_empty(header):
                transactions: List[BaseTransaction] = []
                uncles: List[BlockHeader] = []
            else:
                body = self._pending_bodies.pop(header)
                uncles = body.uncles

                # transaction data was already persisted in _block_body_bundle_processing, but
                # we need to include the transactions for them to be added to the hash->txn lookup
                tx_class = block_class.get_transaction_class()
                transactions = [tx_class.from_base_transaction(tx) for tx in body.transactions]

            block = block_class(header, transactions, uncles)
            await self.wait(self.db.coro_persist_block(block))

    async def _assign_receipt_download_to_peers(self) -> None:
        """
        Loop indefinitely, assigning idle peers to download receipts needed for syncing.
        """
        while self.is_operational:
            # from all the peers that are not currently downloading receipts, get the fastest
            peer = await self.wait(self._receipt_peers.get_fastest())

            # get headers for receipts that we need to download, preferring lowest block number
            batch_id, headers = await self.wait(self._receipt_tasks.get(MAX_RECEIPTS_FETCH))

            # schedule the receipt download and move on
            peer.run_task(self._run_receipt_download_batch(peer, batch_id, headers))

    def _mark_body_download_complete(
            self,
            batch_id: int,
            completed_headers: Tuple[BlockHeader, ...]) -> None:
        super()._mark_body_download_complete(batch_id, completed_headers)
        self._block_persist_tracker.finish_prereq(
            BlockPersistPrereqs.StoreBlockBodies,
            completed_headers,
        )

    async def _run_receipt_download_batch(
            self,
            peer: ETHPeer,
            batch_id: int,
            headers: Tuple[BlockHeader, ...]) -> None:
        """
        Given a single batch retrieved from self._receipt_tasks, get as many of the receipt bundles
        as possible, and mark them as complete.
        """
        # If there is an exception during _process_receipts, prepare to mark the task as finished
        # with no headers collected:
        completed_headers: Tuple[BlockHeader, ...] = tuple()
        try:
            completed_headers = await peer.wait(self._process_receipts(peer, headers))

            self._block_persist_tracker.finish_prereq(
                BlockPersistPrereqs.StoreReceipts,
                completed_headers,
            )
        except BaseP2PError as exc:
            self.logger.info("Unexpected p2p perror while downloading receipt from peer: %s", exc)
            self.logger.debug("Problem downloading receipt from peer, dropping...", exc_info=True)
        else:
            # peer completed successfully, so have it get back in line for processing
            if len(completed_headers) > 0:
                # peer completed successfully, so have it get back in line for processing
                self._receipt_peers.put_nowait(peer)
            else:
                # peer returned no results, wait a while before trying again
                delay = self.EMPTY_PEER_RESPONSE_PENALTY
                self.logger.debug("Pausing %s for %.1fs, for sending 0 receipts", peer, delay)
                self.call_later(delay, self._receipt_peers.put_nowait, peer)
        finally:
            self._receipt_tasks.complete(batch_id, completed_headers)

    async def _block_body_bundle_processing(self, bundles: Tuple[BlockBodyBundle, ...]) -> None:
        """
        Fast sync writes all the block body bundle data directly to the database,
        in order to make it... fast.
        """
        for (_, (_, trie_data_dict), _) in bundles:
            await self.wait(self.db.coro_persist_trie_data_dict(trie_data_dict))

    async def _process_receipts(
            self,
            peer: ETHPeer,
            all_headers: Tuple[BlockHeader, ...]) -> Tuple[BlockHeader, ...]:
        """
        Downloads and persists the receipts for the given set of block headers.
        Some receipts may be trivial, having a blank root hash, and will not be requested.

        :param peer: to issue the receipt request to
        :param all_headers: attempt to get receipts for as many of these headers as possible
        :return: the headers for receipts that were successfully downloaded (or were trivial)
        """
        # Post-Byzantium blocks may have identical receipt roots (e.g. when they have the same
        # number of transactions and all succeed/failed: ropsten blocks 2503212 and 2503284),
        # so we do this to avoid requesting the same receipts multiple times.

        # combine headers with the same receipt root, so we can mark them as completed, later
        receipt_root_to_headers = groupby(attrgetter('receipt_root'), all_headers)

        # Ignore headers that have an empty receipt root
        trivial_headers = tuple(receipt_root_to_headers.pop(BLANK_ROOT_HASH, tuple()))

        # pick one of the headers for each missing receipt root
        unique_headers_needed = tuple(
            first(headers)
            for root, headers in receipt_root_to_headers.items()
        )

        if not unique_headers_needed:
            return trivial_headers

        receipt_bundles = await self._request_receipts(peer, unique_headers_needed)

        if not receipt_bundles:
            return trivial_headers

        try:
            await self._validate_receipts(unique_headers_needed, receipt_bundles)
        except ValidationError as err:
            self.logger.info(
                "Disconnecting from %s: sent invalid receipt: %s",
                peer,
                err,
            )
            await peer.disconnect(DisconnectReason.bad_protocol)
            return trivial_headers

        # process all of the returned receipts, storing their trie data
        # dicts in the database
        receipts, trie_roots_and_data_dicts = zip(*receipt_bundles)
        receipt_roots, trie_data_dicts = zip(*trie_roots_and_data_dicts)
        for trie_data in trie_data_dicts:
            await self.wait(self.db.coro_persist_trie_data_dict(trie_data))

        # Identify which headers have the receipt roots that are now complete.
        completed_header_groups = tuple(
            headers
            for root, headers in receipt_root_to_headers.items()
            if root in receipt_roots
        )
        newly_completed_headers = tuple(concat(completed_header_groups))

        self.logger.debug(
            "Got receipts for %d/%d headers from %s, with %d trivial headers",
            len(newly_completed_headers),
            len(all_headers) - len(trivial_headers),
            peer,
            len(trivial_headers),
        )
        return newly_completed_headers + trivial_headers

    async def _validate_receipts(
            self,
            headers: Tuple[BlockHeader, ...],
            receipt_bundles: Tuple[ReceiptBundle, ...]) -> None:

        header_by_root = {
            header.receipt_root: header
            for header in headers
            if not _is_receipts_empty(header)
        }
        receipts_by_root = {
            receipt_root: receipts
            for (receipts, (receipt_root, _))
            in receipt_bundles
            if receipt_root != BLANK_ROOT_HASH
        }
        for receipt_root, header in header_by_root.items():
            if receipt_root not in receipts_by_root:
                # this receipt group was not returned by the peer, skip validation
                continue
            for receipt in receipts_by_root[receipt_root]:
                await self.chain.coro_validate_receipt(receipt, header)

    async def _request_receipts(
            self,
            peer: ETHPeer,
            batch: Tuple[BlockHeader, ...]) -> Tuple[ReceiptBundle, ...]:
        """
        Requests the batch of receipts from the given peer, returning the
        received receipt data.
        """
        self.logger.debug("Requesting receipts for %d headers from %s", len(batch), peer)
        try:
            receipt_bundles = await peer.requests.get_receipts(batch)
        except TimeoutError as err:
            self.logger.debug(
                "Timed out requesting receipts for %d headers from %s", len(batch), peer,
            )
            return tuple()
        except CancelledError:
            self.logger.debug("Pending receipts call to %r future cancelled", peer)
            return tuple()
        except OperationCancelled:
            self.logger.trace("Pending receipts call to %r operation cancelled", peer)
            return tuple()
        except PeerConnectionLost:
            self.logger.debug("Peer went away, cancelling the receipts request and moving on...")
            return tuple()
        except Exception:
            self.logger.exception("Unknown error when getting receipts")
            raise

        if not receipt_bundles:
            return tuple()

        return receipt_bundles


class BlockImportPrereqs(enum.Enum):
    StoreBlockBodies = enum.auto()


class RegularChainSyncer(BaseBodyChainSyncer):
    """
    Sync with the Ethereum network by fetching block headers/bodies and importing them.

    Here, the run() method will execute the sync loop forever, until our CancelToken is triggered.
    """
    def __init__(self,
                 chain: AsyncChain,
                 db: AsyncHeaderDB,
                 peer_pool: ETHPeerPool,
                 token: CancelToken = None) -> None:
        super().__init__(chain, db, peer_pool, token)

        self._body_peers = WaitingPeers(commands.BlockBodies)

        # track when block bodies are downloaded, so that blocks can be imported
        self._block_import_tracker = OrderedTaskPreparation(
            BlockImportPrereqs,
            id_extractor=attrgetter('hash'),
            # make sure that a block is not imported until the parent block is imported
            dependency_extractor=attrgetter('parent_hash'),
        )

    async def _run(self) -> None:
        head = await self.wait(self.db.coro_get_canonical_head())
        self._block_import_tracker.set_finished_dependency(head)
        self.run_daemon_task(self._launch_prerequisite_tasks())
        self.run_daemon_task(self._assign_body_download_to_peers())
        self.run_daemon_task(self._import_ready_blocks())
        await super()._run()

    def register_peer(self, peer: BasePeer) -> None:
        # when a new peer is added to the pool, add it to the idle peer list
        super().register_peer(peer)
        self._body_peers.put_nowait(cast(ETHPeer, peer))

    async def _launch_prerequisite_tasks(self) -> None:
        """
        Watch for new headers to be added to the queue, and add the prerequisite
        tasks (downloading block bodies) as they become available.
        """
        while self.is_operational:
            batch_id, headers = await self.wait(self.header_queue.get())

            self._block_import_tracker.register_tasks(headers)

            new_headers = tuple(h for h in headers if h not in self._block_body_tasks)

            # if the output queue gets full, hang until there is room
            await self.wait(self._block_body_tasks.add(new_headers))
            self.header_queue.complete(batch_id, headers)

    def _mark_body_download_complete(
            self,
            batch_id: int,
            completed_headers: Tuple[BlockHeader, ...]) -> None:
        super()._mark_body_download_complete(batch_id, completed_headers)
        self._block_import_tracker.finish_prereq(
            BlockImportPrereqs.StoreBlockBodies,
            completed_headers,
        )

    async def _import_ready_blocks(self) -> None:
        """
        Wait for block bodies to be downloaded, then import the blocks.
        """
        while self.is_operational:
            timer = Timer()

            # wait for block bodies to become ready for execution
            completed_headers = await self.wait(self._block_import_tracker.ready_tasks())

            await self._import_blocks(completed_headers)

            head = await self.wait(self.db.coro_get_canonical_head())
            self.logger.info(
                "Synced chain segment with %d blocks in %.2f seconds, new head: #%d",
                len(completed_headers),
                timer.elapsed,
                head.block_number,
            )

    async def _import_blocks(self, headers: Tuple[BlockHeader, ...]) -> None:
        """
        Import the blocks for the corresponding headers

        :param headers: headers that have the block bodies downloaded
        """
        for header in headers:
            vm_class = self.chain.get_vm_class(header)
            block_class = vm_class.get_block_class()

            if _is_body_empty(header):
                transactions: List[BaseTransaction] = []
                uncles: List[BlockHeader] = []
            else:
                body = self._pending_bodies.pop(header)
                tx_class = block_class.get_transaction_class()
                transactions = [tx_class.from_base_transaction(tx)
                                for tx in body.transactions]
                uncles = body.uncles

            block = block_class(header, transactions, uncles)
            timer = Timer()
            _, new_canonical_blocks, old_canonical_blocks = await self.wait(
                self.chain.coro_import_block(block, perform_validation=True)
            )

            if new_canonical_blocks == (block,):
                # simple import of a single new block.
                self.logger.info("Imported block %d (%d txs) in %.2f seconds",
                                 block.number, len(transactions), timer.elapsed)
            elif not new_canonical_blocks:
                # imported block from a fork.
                self.logger.info("Imported non-canonical block %d (%d txs) in %.2f seconds",
                                 block.number, len(transactions), timer.elapsed)
            elif old_canonical_blocks:
                self.logger.info(
                    "Chain Reorganization: Imported block %d (%d txs) in %.2f "
                    "seconds, %d blocks discarded and %d new canonical blocks added",
                    block.number,
                    len(transactions),
                    timer.elapsed,
                    len(old_canonical_blocks),
                    len(new_canonical_blocks),
                )
            else:
                raise Exception("Invariant: unreachable code path")


def _is_body_empty(header: BlockHeader) -> bool:
    return header.transaction_root == BLANK_ROOT_HASH and header.uncles_hash == EMPTY_UNCLE_HASH


def _is_receipts_empty(header: BlockHeader) -> bool:
    return header.receipt_root == BLANK_ROOT_HASH
