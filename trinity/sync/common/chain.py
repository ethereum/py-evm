import asyncio
from abc import abstractmethod
from typing import (
    AsyncGenerator,
    Tuple,
    Union,
    cast,
)

from cancel_token import CancelToken, OperationCancelled

from eth.constants import GENESIS_BLOCK_NUMBER
from eth.chains import AsyncChain
from eth.exceptions import (
    HeaderNotFound,
)
from eth_typing import (
    Hash32,
)
from eth_utils import (
    ValidationError,
)
from eth.rlp.headers import BlockHeader

from p2p import protocol
from p2p.constants import MAX_REORG_DEPTH, SEAL_CHECK_RANDOM_SAMPLE_RATE
from p2p.p2p_proto import DisconnectReason
from p2p.peer import BasePeer, PeerPool, PeerSubscriber
from p2p.service import BaseService

from trinity.db.header import AsyncHeaderDB
from trinity.p2p.handlers import PeerRequestHandler
from trinity.protocol.eth.peer import ETHPeer
from trinity.protocol.les.peer import LESPeer


HeaderRequestingPeer = Union[LESPeer, ETHPeer]


class BaseHeaderChainSyncer(BaseService, PeerSubscriber):
    """
    Sync with the Ethereum network by fetching/storing block headers.

    Here, the run() method will execute the sync loop until our local head is the same as the one
    with the highest TD announced by any of our peers.
    """
    # We'll only sync if we are connected to at least min_peers_to_sync.
    min_peers_to_sync = 1
    # Post-processing steps can exit out of sync (for example, fast sync) by triggering this token:
    complete_token = None
    # TODO: Instead of a fixed timeout, we should use a variable one that gets adjusted based on
    # the round-trip times from our download requests.
    _reply_timeout = 60
    _seal_check_random_sample_rate = SEAL_CHECK_RANDOM_SAMPLE_RATE
    # the latest header hash of the peer on the current sync
    _target_header_hash = None

    def __init__(self,
                 chain: AsyncChain,
                 db: AsyncHeaderDB,
                 peer_pool: PeerPool,
                 token: CancelToken = None) -> None:
        self.complete_token = CancelToken('trinity.sync.common.BaseHeaderChainSyncer.SyncCompleted')
        if token is None:
            super_service_token = self.complete_token
        else:
            super_service_token = token.chain(self.complete_token)
        super().__init__(super_service_token)
        self.chain = chain
        self.db = db
        self.peer_pool = peer_pool
        self._handler = PeerRequestHandler(self.db, self.logger, self.cancel_token)
        self._syncing = False
        self._sync_complete = asyncio.Event()
        self._sync_requests: asyncio.Queue[HeaderRequestingPeer] = asyncio.Queue()

        # pending queue size should be big enough to avoid starving the processing consumers, but
        # small enough to avoid wasteful over-requests before post-processing can happen
        max_pending_headers = ETHPeer.max_headers_fetch * 5
        self.pending_headers: asyncio.Queue[BlockHeader] = asyncio.Queue(max_pending_headers)

    @property
    def msg_queue_maxsize(self) -> int:
        # This is a rather arbitrary value, but when the sync is operating normally we never see
        # the msg queue grow past a few hundred items, so this should be a reasonable limit for
        # now.
        return 2000

    def get_target_header_hash(self) -> Hash32:
        if self._target_header_hash is None:
            raise ValueError("Cannot check the target hash when there is no active sync")
        else:
            return self._target_header_hash

    def register_peer(self, peer: BasePeer) -> None:
        self._sync_requests.put_nowait(cast(HeaderRequestingPeer, self.peer_pool.highest_td_peer))

    async def _handle_msg_loop(self) -> None:
        while self.is_operational:
            peer, cmd, msg = await self.wait(self.msg_queue.get())
            # Our handle_msg() method runs cpu-intensive tasks in sub-processes so that the main
            # loop can keep processing msgs, and that's why we use self.run_task() instead of
            # awaiting for it to finish here.
            self.run_task(self.handle_msg(cast(HeaderRequestingPeer, peer), cmd, msg))

    async def handle_msg(self, peer: HeaderRequestingPeer, cmd: protocol.Command,
                         msg: protocol._DecodedMsgType) -> None:
        try:
            await self._handle_msg(peer, cmd, msg)
        except OperationCancelled:
            # Silently swallow OperationCancelled exceptions because otherwise they'll be caught
            # by the except below and treated as unexpected.
            pass
        except Exception:
            self.logger.exception("Unexpected error when processing msg from %s", peer)

    async def _run(self) -> None:
        self.run_task(self._handle_msg_loop())
        with self.subscribe(self.peer_pool):
            while self.is_operational:
                try:
                    peer = await self.wait(self._sync_requests.get())
                except OperationCancelled:
                    # In the case of a fast sync, we return once the sync is completed, and our
                    # caller must then run the StateDownloader.
                    return
                else:
                    self.run_task(self.sync(peer))

    async def sync(self, peer: HeaderRequestingPeer) -> None:
        if self._syncing:
            self.logger.debug(
                "Got a NewBlock or a new peer, but already syncing so doing nothing")
            return
        elif len(self.peer_pool) < self.min_peers_to_sync:
            self.logger.info(
                "Connected to less peers (%d) than the minimum (%d) required to sync, "
                "doing nothing", len(self.peer_pool), self.min_peers_to_sync)
            return

        self._syncing = True
        try:
            await self._sync(peer)
        except OperationCancelled as e:
            self.logger.info("Sync with %s aborted: %s", peer, e)
        finally:
            self._syncing = False

    async def _sync(self, peer: HeaderRequestingPeer) -> None:
        """Try to fetch/process blocks until the given peer's head_hash.

        Returns when the peer's head_hash is available in our ChainDB, or if any error occurs
        during the sync.

        If in fast-sync mode, the _sync_completed event will be set upon successful completion of
        a sync.
        """
        head = await self.wait(self.db.coro_get_canonical_head())
        head_td = await self.wait(self.db.coro_get_score(head.hash))
        if peer.head_td <= head_td:
            self.logger.info(
                "Head TD (%d) announced by %s not higher than ours (%d), not syncing",
                peer.head_td, peer, head_td)
            return

        self.logger.info("Starting sync with %s", peer)
        # When we start the sync with a peer, we always request up to MAX_REORG_DEPTH extra
        # headers before our current head's number, in case there were chain reorgs since the last
        # time _sync() was called. All of the extra headers that are already present in our DB
        # will be discarded by _fetch_missing_headers() so we don't unnecessarily process them
        # again.
        start_at = max(GENESIS_BLOCK_NUMBER + 1, head.block_number - MAX_REORG_DEPTH)
        while self.is_operational:
            if not peer.is_operational:
                self.logger.info("%s disconnected, aborting sync", peer)
                break

            try:
                fetch_headers_coro = self._fetch_missing_headers(peer, start_at)
                headers = await self.complete_token.cancellable_wait(fetch_headers_coro)
            except OperationCancelled:
                self.logger.info("Sync with %s completed", peer)
                break
            except TimeoutError:
                self.logger.warn("Timeout waiting for header batch from %s, aborting sync", peer)
                await peer.disconnect(DisconnectReason.timeout)
                break
            except ValidationError as err:
                self.logger.warn(
                    "Invalid header response sent by peer %s disconnecting: %s",
                    peer, err,
                )
                await peer.disconnect(DisconnectReason.useless_peer)
                break

            if not headers:
                self.logger.info("Got no new headers from %s, aborting sync", peer)
                break

            first = headers[0]
            try:
                await self.wait(self.db.coro_get_block_header_by_hash(first.parent_hash))
            except HeaderNotFound:
                self.logger.warn("Unable to find common ancestor betwen our chain and %s", peer)
                break

            self.logger.debug("Got new header chain starting at #%d", first.block_number)
            try:
                await self.chain.coro_validate_chain(headers, self._seal_check_random_sample_rate)
            except ValidationError as e:
                self.logger.warn("Received invalid headers from %s, aborting sync: %s", peer, e)
                break

            # Setting the latest header hash for the peer, before queuing header processing tasks
            self._target_header_hash = peer.head_hash

            await self._queue_headers_for_processing(headers)
            start_at = headers[-1].block_number + 1

    async def _queue_headers_for_processing(self, headers: Tuple[BlockHeader, ...]) -> None:
        # this block is an optimization to avoid lots of await calls
        if len(headers) + self.pending_headers.qsize() <= self.pending_headers.maxsize:
            for header in headers:
                self.pending_headers.put_nowait(header)
        else:
            for header in headers:
                await self.pending_headers.put(header)

    async def _fetch_missing_headers(
            self, peer: HeaderRequestingPeer, start_at: int) -> Tuple[BlockHeader, ...]:
        """Fetch a batch of headers starting at start_at and return the ones we're missing."""
        self.logger.debug("Fetching chain segment starting at #%d", start_at)

        headers = await peer.requests.get_block_headers(
            start_at,
            peer.max_headers_fetch,
            skip=0,
            reverse=False,
        )

        # We only want headers that are missing, so we iterate over the list
        # until we find the first missing header, after which we return all of
        # the remaining headers.
        async def get_missing_tail(self: 'BaseHeaderChainSyncer',
                                   headers: Tuple[BlockHeader, ...]
                                   ) -> AsyncGenerator[BlockHeader, None]:
            iter_headers = iter(headers)
            for header in iter_headers:
                is_missing = not await self.wait(self.db.coro_header_exists(header.hash))
                if is_missing:
                    yield header
                    break
                else:
                    self.logger.debug("Discarding header that we already have: %s", header)

            for header in iter_headers:
                yield header

        # The inner list comprehension is needed because async_generators
        # cannot be cast to a tuple.
        tail_headers = tuple([header async for header in get_missing_tail(self, headers)])

        return tail_headers

    async def pop_all_pending_headers(self) -> Tuple[BlockHeader, ...]:
        """Get all the currently pending headers. If no headers pending, wait until one is"""
        queue = self.pending_headers
        if queue.empty():
            first_header = await queue.get()
        else:
            first_header = queue.get_nowait()

        available = queue.qsize()
        return (first_header, ) + tuple(queue.get_nowait() for _ in range(available))

    @abstractmethod
    async def _handle_msg(self, peer: HeaderRequestingPeer, cmd: protocol.Command,
                          msg: protocol._DecodedMsgType) -> None:
        raise NotImplementedError("Must be implemented by subclasses")
