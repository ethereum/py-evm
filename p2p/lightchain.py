import asyncio
import logging
import time
from typing import (  # noqa: F401
    Any,
    cast,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TYPE_CHECKING,
)

from evm.constants import GENESIS_BLOCK_NUMBER
from evm.rlp.headers import BlockHeader

from p2p.exceptions import (
    EmptyGetBlockHeadersReply,
    LESAnnouncementProcessingError,
    OperationCancelled,
    TooManyTimeouts,
    UnexpectedMessage,
)
from p2p import les
from p2p.cancel_token import (
    CancelToken,
    wait_with_token,
)
from p2p.peer import (
    BasePeer,
    LESPeer,
    PeerPool,
    PeerPoolSubscriber,
)

if TYPE_CHECKING:
    from trinity.db.header import BaseAsyncHeaderDB  # noqa: F401


class LightChain(PeerPoolSubscriber):
    logger = logging.getLogger("p2p.lightchain.LightChain")
    max_consecutive_timeouts = 5
    headerdb: 'BaseAsyncHeaderDB' = None

    def __init__(self, headerdb: 'BaseAsyncHeaderDB', peer_pool: PeerPool) -> None:
        self.headerdb = headerdb
        self.peer_pool = peer_pool
        self._announcement_queue = asyncio.Queue()  # type: asyncio.Queue[Tuple[LESPeer, les.HeadInfo]]  # noqa: E501
        self._last_processed_announcements = {}  # type: Dict[LESPeer, les.HeadInfo]
        self.cancel_token = CancelToken('LightChain')
        self._running_peers = set()  # type: Set[LESPeer]

    def register_peer(self, peer: BasePeer) -> None:
        asyncio.ensure_future(self.handle_peer(cast(LESPeer, peer)))

    async def handle_peer(self, peer: LESPeer) -> None:
        """Handle the lifecycle of the given peer.

        Returns when the peer is finished or when the LightChain is asked to stop.
        """
        self._running_peers.add(peer)
        try:
            await self._handle_peer(peer)
        finally:
            self._running_peers.remove(peer)

    async def _handle_peer(self, peer: LESPeer) -> None:
        self._announcement_queue.put_nowait((peer, peer.head_info))
        while True:
            try:
                cmd, msg = await peer.read_sub_proto_msg(self.cancel_token)
            except OperationCancelled:
                # Either the peer disconnected or our cancel_token has been triggered, so break
                # out of the loop to stop attempting to sync with this peer.
                break
            # We currently implement only the LES commands for retrieving data (apart from
            # Announce), and those should always come as a response to requests we make so will be
            # handled by LESPeer.handle_sub_proto_msg().
            if isinstance(cmd, les.Announce):
                peer.head_info = cmd.as_head_info(msg)
                self._announcement_queue.put_nowait((peer, peer.head_info))
            else:
                raise UnexpectedMessage("Unexpected msg from {}: {}".format(peer, msg))

        await self.drop_peer(peer)
        self.logger.debug("%s finished", peer)

    async def drop_peer(self, peer: LESPeer) -> None:
        self._last_processed_announcements.pop(peer, None)
        await peer.cancel()

    async def wait_until_finished(self):
        start_at = time.time()
        # Wait at most 5 seconds for pending peers to finish.
        while time.time() < start_at + 5:
            if not self._running_peers:
                break
            self.logger.debug("Waiting for %d running peers to finish", len(self._running_peers))
            await asyncio.sleep(0.1)
        else:
            self.logger.info("Waited too long for peers to finish, exiting anyway")

    async def get_best_peer(self) -> LESPeer:
        """
        Return the peer with the highest announced block height.
        """
        while not self.peer_pool.peers:
            self.logger.debug("No connected peers, sleeping a bit")
            await asyncio.sleep(0.5)

        def peer_block_height(peer: LESPeer) -> int:
            last_announced = self._last_processed_announcements.get(peer)
            if last_announced is None:
                return -1
            return last_announced.block_number

        # TODO: Should pick a random one in case there are multiple peers with the same block
        # height.
        return max(
            [cast(LESPeer, peer) for peer in self.peer_pool.peers],
            key=peer_block_height)

    async def wait_for_announcement(self) -> Tuple[LESPeer, les.HeadInfo]:
        """Wait for a new announcement from any of our connected peers.

        Returns a tuple containing the LESPeer on which the announcement was received and the
        announcement info.

        Raises OperationCancelled when LightChain.stop() has been called.
        """
        # Wait for either a new announcement or our cancel_token to be triggered.
        return await wait_with_token(self._announcement_queue.get(), token=self.cancel_token)

    async def run(self) -> None:
        """Run the LightChain, ensuring headers are in sync with connected peers.

        If .stop() is called, we'll disconnect from all peers and return.
        """
        self.logger.info("Running LightChain...")
        self.peer_pool.subscribe(self)
        while True:
            try:
                peer, head_info = await self.wait_for_announcement()
            except OperationCancelled:
                self.logger.debug("Asked to stop, breaking out of run() loop")
                break

            try:
                await self.process_announcement(peer, head_info)
                self._last_processed_announcements[peer] = head_info
            except OperationCancelled:
                self.logger.debug("Asked to stop, breaking out of run() loop")
                break
            except LESAnnouncementProcessingError as e:
                self.logger.warning(repr(e))
                await self.drop_peer(peer)
            except Exception as e:
                self.logger.exception("Unexpected error when processing announcement")
                await self.drop_peer(peer)

    async def fetch_headers(self, start_block: int, peer: LESPeer) -> List[BlockHeader]:
        for i in range(self.max_consecutive_timeouts):
            try:
                return await peer.fetch_headers_starting_at(start_block, self.cancel_token)
            except TimeoutError:
                self.logger.info(
                    "Timeout when fetching headers from %s (attempt %d of %d)",
                    peer, i + 1, self.max_consecutive_timeouts)
                # TODO: Figure out what's a good value to use here.
                await asyncio.sleep(0.5)
        raise TooManyTimeouts()

    async def get_sync_start_block(self, peer: LESPeer, head_info: les.HeadInfo) -> int:
        chain_head = await self.headerdb.coro_get_canonical_head()
        last_peer_announcement = self._last_processed_announcements.get(peer)
        if chain_head.block_number == GENESIS_BLOCK_NUMBER:
            start_block = GENESIS_BLOCK_NUMBER
        elif last_peer_announcement is None:
            # It's the first time we hear from this peer, need to figure out which headers to
            # get from it.  We can't simply fetch headers starting from our current head
            # number because there may have been a chain reorg, so we fetch some headers prior
            # to our head from the peer, and insert any missing ones in our DB, essentially
            # making our canonical chain identical to the peer's up to
            # chain_head.block_number.
            oldest_ancestor_to_consider = max(
                0, chain_head.block_number - peer.max_headers_fetch + 1)
            try:
                headers = await self.fetch_headers(oldest_ancestor_to_consider, peer)
            except EmptyGetBlockHeadersReply:
                raise LESAnnouncementProcessingError(
                    "No common ancestors found between us and {}".format(peer))
            except TooManyTimeouts:
                raise LESAnnouncementProcessingError(
                    "Too many timeouts when fetching headers from {}".format(peer))
            for header in headers:
                await self.headerdb.coro_persist_header(header)
            start_block = chain_head.block_number
        else:
            start_block = last_peer_announcement.block_number - head_info.reorg_depth
        return start_block

    # TODO: Distribute requests among our peers, ensuring the selected peer has the info we want
    # and respecting the flow control rules.
    async def process_announcement(self, peer: LESPeer, head_info: les.HeadInfo) -> None:
        if await self.headerdb.coro_header_exists(head_info.block_hash):
            self.logger.debug(
                "Skipping processing of %s from %s as head has already been fetched",
                head_info, peer)
            return

        start_block = await self.get_sync_start_block(peer, head_info)
        while start_block < head_info.block_number:
            try:
                # We should use "start_block + 1" here, but we always re-fetch the last synced
                # block to work around https://github.com/ethereum/go-ethereum/issues/15447
                batch = await self.fetch_headers(start_block, peer)
            except TooManyTimeouts:
                raise LESAnnouncementProcessingError(
                    "Too many timeouts when fetching headers from {}".format(peer))
            for header in batch:
                await self.headerdb.coro_persist_header(header)
                start_block = header.block_number
            self.logger.info("synced headers up to #%s", start_block)

    async def stop(self):
        self.logger.info("Stopping LightChain...")
        self.cancel_token.trigger()
        self.logger.debug("Waiting for all pending tasks to finish...")
        await self.wait_until_finished()
        self.logger.debug("LightChain finished")
