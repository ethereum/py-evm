import asyncio
import logging
from typing import (
    Any,
    Callable,
    cast,
    Dict,
    List,
    Tuple,
    TYPE_CHECKING,
)

from async_lru import alru_cache

import rlp

from eth_typing import (
    Address,
    Hash32,
)

from eth_hash.auto import keccak

from eth_utils import (
    encode_hex,
)

from trie import HexaryTrie

from evm.constants import GENESIS_BLOCK_NUMBER
from evm.exceptions import BlockNotFound, HeaderNotFound
from evm.rlp.accounts import Account
from evm.rlp.headers import BlockHeader
from evm.rlp.receipts import Receipt

from p2p.exceptions import (
    BadLESResponse,
    EmptyGetBlockHeadersReply,
    LESAnnouncementProcessingError,
    OperationCancelled,
    TooManyTimeouts,
)
from p2p import les
from p2p import protocol
from p2p.constants import REPLY_TIMEOUT
from p2p.peer import (
    BasePeer,
    LESPeer,
    PeerPool,
    PeerPoolSubscriber,
)
from p2p.rlp import BlockBody
from p2p.service import (
    BaseService,
)
from p2p.utils import gen_request_id

if TYPE_CHECKING:
    from trinity.db.header import BaseAsyncHeaderDB  # noqa: F401


class LightPeerChain(PeerPoolSubscriber, BaseService):
    logger = logging.getLogger("p2p.lightchain.LightPeerChain")
    max_consecutive_timeouts = 5
    reply_timeout = REPLY_TIMEOUT
    headerdb: 'BaseAsyncHeaderDB' = None

    def __init__(self, headerdb: 'BaseAsyncHeaderDB', peer_pool: PeerPool) -> None:
        super().__init__()
        self.headerdb = headerdb
        self.peer_pool = peer_pool
        self._announcement_queue: asyncio.Queue[Tuple[LESPeer, les.HeadInfo]] = asyncio.Queue()
        self._last_processed_announcements: Dict[LESPeer, les.HeadInfo] = {}
        self._pending_replies: Dict[int, Callable[[protocol._DecodedMsgType], None]] = {}

    def register_peer(self, peer: BasePeer) -> None:
        peer = cast(LESPeer, peer)
        self._announcement_queue.put_nowait((peer, peer.head_info))

    async def drop_peer(self, peer: LESPeer) -> None:
        self._last_processed_announcements.pop(peer, None)
        await peer.cancel()

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
        return await self.wait_first(self._announcement_queue.get())

    async def _run(self) -> None:
        """Run the LightPeerChain, ensuring headers are in sync with connected peers.

        If .stop() is called, we'll disconnect from all peers and return.
        """
        self.logger.info("Running LightPeerChain...")
        with self.subscribe(self.peer_pool):
            asyncio.ensure_future(self._process_announcements())
            while True:
                peer, cmd, msg = await self.wait_first(self.msg_queue.get())

                if isinstance(cmd, les.Announce):
                    peer.head_info = cmd.as_head_info(msg)
                    self._announcement_queue.put_nowait((peer, peer.head_info))
                elif isinstance(msg, dict):
                    request_id = msg.get('request_id')
                    # request_id can be None here because not all LES messages include one. For
                    # instance, the Announce msg doesn't.
                    if request_id is not None and request_id in self._pending_replies:
                        # This is a reply we're waiting for, so we consume it by passing it to the
                        # registered callback.
                        callback = self._pending_replies.pop(request_id)
                        callback(msg)
                else:
                    self.logger.warn("Unexpected msg from %s: %s (%s)", peer, cmd, msg)

    async def _process_announcements(self) -> None:
        while self.is_running:
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
                return await self._fetch_headers_starting_at(peer, start_block)
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

    async def _wait_for_reply(self, request_id: int) -> Dict[str, Any]:
        reply = None
        got_reply = asyncio.Event()

        def callback(r):
            nonlocal reply
            reply = r
            got_reply.set()

        self._pending_replies[request_id] = callback
        await self.wait_first(got_reply.wait(), timeout=self.reply_timeout)
        return reply

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        peer = await self.get_best_peer()
        return await self._get_block_header_by_hash(peer, block_hash)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_block_body_by_hash(self, block_hash: Hash32) -> BlockBody:
        peer = await self.get_best_peer()
        self.logger.debug("Fetching block %s from %s", encode_hex(block_hash), peer)
        request_id = gen_request_id()
        peer.sub_proto.send_get_block_bodies([block_hash], request_id)
        reply = await self._wait_for_reply(request_id)
        if not reply['bodies']:
            raise BlockNotFound("Peer {} has no block with hash {}".format(peer, block_hash))
        return reply['bodies'][0]

    # TODO add a get_receipts() method to BaseChain API, and dispatch to this, as needed

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_receipts(self, block_hash: Hash32) -> List[Receipt]:
        peer = await self.get_best_peer()
        self.logger.debug("Fetching %s receipts from %s", encode_hex(block_hash), peer)
        request_id = gen_request_id()
        peer.sub_proto.send_get_receipts(block_hash, request_id)
        reply = await self._wait_for_reply(request_id)
        if not reply['receipts']:
            raise BlockNotFound("No block with hash {} found".format(block_hash))
        return reply['receipts'][0]

    # TODO implement AccountDB exceptions that provide the info needed to
    # request accounts and code (and storage?)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_account(self, block_hash: Hash32, address: Address) -> Account:
        peer = await self.get_best_peer()
        key = keccak(address)
        proof = await self._get_proof(peer, block_hash, account_key=b'', key=key)
        header = await self._get_block_header_by_hash(peer, block_hash)
        rlp_account = HexaryTrie.get_from_proof(header.state_root, key, proof)
        return rlp.decode(rlp_account, sedes=Account)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_contract_code(self, block_hash: Hash32, key: bytes) -> bytes:
        peer = await self.get_best_peer()
        request_id = gen_request_id()
        peer.sub_proto.send_get_contract_code(block_hash, key, request_id)
        reply = await self._wait_for_reply(request_id)
        if not reply['codes']:
            return b''
        return reply['codes'][0]

    async def _get_block_header_by_hash(self, peer: LESPeer, block_hash: Hash32) -> BlockHeader:
        self.logger.debug("Fetching header %s from %s", encode_hex(block_hash), peer)
        request_id = gen_request_id()
        max_headers = 1
        peer.sub_proto.send_get_block_headers(block_hash, max_headers, request_id)
        reply = await self._wait_for_reply(request_id)
        if not reply['headers']:
            raise HeaderNotFound("Peer {} has no block with hash {}".format(peer, block_hash))
        header = reply['headers'][0]
        if header.hash != block_hash:
            raise BadLESResponse(
                "Received header hash (%s) does not match what we requested (%s)",
                header.hex_hash, encode_hex(block_hash))
        return header

    async def _get_proof(self,
                         peer: LESPeer,
                         block_hash: bytes,
                         account_key: bytes,
                         key: bytes,
                         from_level: int = 0) -> List[bytes]:
        request_id = gen_request_id()
        peer.sub_proto.send_get_proof(block_hash, account_key, key, from_level, request_id)
        reply = await self._wait_for_reply(request_id)
        return reply['proof']

    async def _fetch_headers_starting_at(
            self, peer: LESPeer, start_block: int) -> List[BlockHeader]:
        """Fetches up to self.max_headers_fetch starting at start_block.

        Returns a list containing those headers in ascending order of block number.
        """
        request_id = gen_request_id()
        peer.sub_proto.send_get_block_headers(
            start_block, peer.max_headers_fetch, request_id, reverse=False)
        reply = await self._wait_for_reply(request_id)
        if not reply['headers']:
            raise EmptyGetBlockHeadersReply(
                "No headers in reply. start_block=={}".format(start_block))
        self.logger.debug(
            "fetched headers from %s to %s", reply['headers'][0].block_number,
            reply['headers'][-1].block_number)
        return reply['headers']
