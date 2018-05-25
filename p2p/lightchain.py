import asyncio
import logging
from typing import (
    cast,
    Dict,
    List,
    Set,
    Tuple,
    TYPE_CHECKING,
)

from async_lru import alru_cache

from eth_typing import (
    Address,
    Hash32,
)

from eth_utils import (
    encode_hex,
)

from evm.constants import GENESIS_BLOCK_NUMBER
from evm.rlp.accounts import Account
from evm.rlp.blocks import BaseBlock
from evm.rlp.headers import BlockHeader
from evm.rlp.receipts import Receipt

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
from p2p.service import (
    BaseService,
)
from p2p.utils import unclean_close_exceptions

if TYPE_CHECKING:
    from trinity.db.header import BaseAsyncHeaderDB  # noqa: F401


class LightPeerChain(PeerPoolSubscriber, BaseService):
    logger = logging.getLogger("p2p.lightchain.LightPeerChain")
    max_consecutive_timeouts = 5
    headerdb: 'BaseAsyncHeaderDB' = None

    def __init__(self, headerdb: 'BaseAsyncHeaderDB', peer_pool: PeerPool) -> None:
        super().__init__()
        self.headerdb = headerdb
        self.peer_pool = peer_pool
        self._announcement_queue: asyncio.Queue[Tuple[LESPeer, les.HeadInfo]] = asyncio.Queue()
        self._last_processed_announcements: Dict[LESPeer, les.HeadInfo] = {}
        self._running_peers: Set[LESPeer] = set()

    def register_peer(self, peer: BasePeer) -> None:
        asyncio.ensure_future(self.handle_peer(cast(LESPeer, peer)))

    async def handle_peer(self, peer: LESPeer) -> None:
        """Handle the lifecycle of the given peer.

        Returns when the peer is finished or when the LightPeerChain is asked to stop.
        """
        self._running_peers.add(peer)
        # Use a local token that we'll trigger to cleanly cancel the _handle_peer() sub-tasks when
        # self.finished is set.
        peer_token = self.cancel_token.chain(CancelToken("HandlePeer"))
        try:
            await asyncio.wait(
                [self._handle_peer(peer, peer_token), self.finished.wait()],
                return_when=asyncio.FIRST_COMPLETED)
        finally:
            peer_token.trigger()
            self._running_peers.remove(peer)

    async def _handle_peer(self, peer: LESPeer, cancel_token: CancelToken) -> None:
        self._announcement_queue.put_nowait((peer, peer.head_info))
        while not self.is_finished:
            try:
                cmd, msg = await peer.read_sub_proto_msg(cancel_token)
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
        peer_cleanups = [peer.cleaned_up.wait() for peer in self._running_peers]
        await asyncio.gather(*peer_cleanups)

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

        Raises OperationCancelled when LightPeerChain.stop() has been called.
        """
        # Wait for either a new announcement or our cancel_token to be triggered.
        return await wait_with_token(self._announcement_queue.get(), token=self.cancel_token)

    async def _run(self) -> None:
        """Run the LightPeerChain, ensuring headers are in sync with connected peers.

        If .stop() is called, we'll disconnect from all peers and return.
        """
        self.logger.info("Running LightPeerChain...")
        with self.subscribe(self.peer_pool):
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
                except unclean_close_exceptions:
                    self.logger.exception("Unclean exit from LightPeerChain")
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

    async def _cleanup(self):
        self.logger.info("Stopping LightPeerChain...")
        await self.wait_until_finished()
        self.logger.debug("LightPeerChain finished")

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_block_header_by_hash(self, block_hash: Hash32) -> BaseBlock:
        peer = await self.get_best_peer()
        self.logger.debug("Fetching header %s from %s", encode_hex(block_hash), peer)
        return await peer.get_block_header_by_hash(block_hash, self.cancel_token)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_block_body_by_hash(self, block_hash: Hash32) -> BaseBlock:
        peer = await self.get_best_peer()
        self.logger.debug("Fetching block %s from %s", encode_hex(block_hash), peer)
        return await peer.get_block_by_hash(block_hash, self.cancel_token)

    # TODO add a get_receipts() method to BaseChain API, and dispatch to this, as needed

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_receipts(self, block_hash: Hash32) -> List[Receipt]:
        peer = await self.get_best_peer()
        self.logger.debug("Fetching %s receipts from %s", encode_hex(block_hash), peer)
        return await peer.get_receipts(block_hash, self.cancel_token)

    # TODO implement AccountDB exceptions that provide the info needed to
    # request accounts and code (and storage?)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_account(self, block_hash: Hash32, address: Address) -> Account:
        peer = await self.get_best_peer()
        return await peer.get_account(block_hash, address, self.cancel_token)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_contract_code(self, block_hash: Hash32, key: bytes) -> bytes:
        peer = await self.get_best_peer()
        return await peer.get_contract_code(block_hash, key, self.cancel_token)
