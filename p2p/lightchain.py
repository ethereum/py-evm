import asyncio
from typing import (
    Any,
    Callable,
    cast,
    Dict,
    List,
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

from evm.exceptions import (
    BlockNotFound,
    HeaderNotFound,
)
from evm.rlp.accounts import Account
from evm.rlp.headers import BlockHeader
from evm.rlp.receipts import Receipt

from p2p.exceptions import (
    BadLESResponse,
)
from p2p.cancel_token import CancelToken
from p2p import protocol
from p2p.constants import (
    COMPLETION_TIMEOUT,
    REPLY_TIMEOUT,
)
from p2p.p2p_proto import (
    DisconnectReason,
)
from p2p.peer import (
    LESPeer,
    PeerPool,
    PeerPoolSubscriber,
)
from p2p.rlp import BlockBody
from p2p.service import (
    BaseService,
    service_timeout,
)
from p2p.utils import gen_request_id

if TYPE_CHECKING:
    from trinity.db.header import BaseAsyncHeaderDB  # noqa: F401


class LightPeerChain(PeerPoolSubscriber, BaseService):
    reply_timeout = REPLY_TIMEOUT
    headerdb: 'BaseAsyncHeaderDB' = None

    def __init__(
            self,
            headerdb: 'BaseAsyncHeaderDB',
            peer_pool: PeerPool,
            token: CancelToken = None) -> None:
        PeerPoolSubscriber.__init__(self)
        BaseService.__init__(self, token)
        self.headerdb = headerdb
        self.peer_pool = peer_pool
        self._pending_replies: Dict[int, Callable[[protocol._DecodedMsgType], None]] = {}

    async def _run(self) -> None:
        with self.subscribe(self.peer_pool):
            while True:
                peer, cmd, msg = await self.wait(self.msg_queue.get())
                if isinstance(msg, dict):
                    request_id = msg.get('request_id')
                    # request_id can be None here because not all LES messages include one. For
                    # instance, the Announce msg doesn't.
                    if request_id is not None and request_id in self._pending_replies:
                        # This is a reply we're waiting for, so we consume it by passing it to the
                        # registered callback.
                        callback = self._pending_replies.pop(request_id)
                        callback(msg)

    async def _cleanup(self) -> None:
        pass

    async def _wait_for_reply(self, request_id: int) -> Dict[str, Any]:
        reply = None
        got_reply = asyncio.Event()

        def callback(r: protocol._DecodedMsgType) -> None:
            nonlocal reply
            reply = r
            got_reply.set()

        self._pending_replies[request_id] = callback
        await self.wait(got_reply.wait(), timeout=self.reply_timeout)
        # we need to cast here because mypy knows this should actually be of type
        # `protocol._DecodedMsgType`. However, we know the type should be restricted
        # to `Dict[str, Any]` and this is what all callsites expect
        return cast(Dict[str, Any], reply)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        peer = cast(LESPeer, self.peer_pool.highest_td_peer)
        return await self._get_block_header_by_hash(peer, block_hash)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    async def get_block_body_by_hash(self, block_hash: Hash32) -> BlockBody:
        peer = cast(LESPeer, self.peer_pool.highest_td_peer)
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
        peer = cast(LESPeer, self.peer_pool.highest_td_peer)
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
        peer = cast(LESPeer, self.peer_pool.highest_td_peer)
        key = keccak(address)
        proof = await self._get_proof(peer, block_hash, account_key=b'', key=key)
        header = await self._get_block_header_by_hash(peer, block_hash)
        rlp_account = HexaryTrie.get_from_proof(header.state_root, key, proof)
        return rlp.decode(rlp_account, sedes=Account)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    @service_timeout(COMPLETION_TIMEOUT)
    async def get_contract_code(self, block_hash: Hash32, address: Address) -> bytes:
        """
        :param block_hash: find code as of the block with block_hash
        :param address: which contract to look up

        :return: bytecode of the contract, ``b''`` if no code is set
        """
        peer = cast(LESPeer, self.peer_pool.highest_td_peer)
        request_id = gen_request_id()
        peer.sub_proto.send_get_contract_code(block_hash, keccak(address), request_id)
        reply = await self._wait_for_reply(request_id)

        if not reply['codes']:
            bytecode = b''
        else:
            bytecode = reply['codes'][0]

        # validate bytecode against a proven account
        account = await self.get_account(block_hash, address)

        if account.code_hash == keccak(bytecode):
            return bytecode
        else:
            # disconnect from this bad peer
            await self.disconnect_peer(peer, DisconnectReason.subprotocol_error)
            # try again with another peer
            return await self.get_contract_code(block_hash, address)

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
