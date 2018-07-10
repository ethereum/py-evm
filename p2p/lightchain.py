import asyncio
from functools import (
    partial,
)
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
from trie.exceptions import BadTrieProof

from evm.exceptions import (
    BlockNotFound,
    HeaderNotFound,
)
from evm.rlp.accounts import Account
from evm.rlp.headers import BlockHeader
from evm.rlp.receipts import Receipt

from p2p.exceptions import (
    BadLESResponse,
    NoEligiblePeers,
)
from p2p.cancel_token import CancelToken
from p2p import protocol
from p2p.constants import (
    COMPLETION_TIMEOUT,
    MAX_REQUEST_ATTEMPTS,
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
    @service_timeout(COMPLETION_TIMEOUT)
    async def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        peer = cast(LESPeer, self.peer_pool.highest_td_peer)
        return await self._get_block_header_by_hash(peer, block_hash)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    @service_timeout(COMPLETION_TIMEOUT)
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
    @service_timeout(COMPLETION_TIMEOUT)
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
    @service_timeout(COMPLETION_TIMEOUT)
    async def get_account(self, block_hash: Hash32, address: Address) -> Account:
        return await self._retry_on_bad_response(
            partial(self._get_account_from_peer, block_hash, address)
        )

    async def _get_account_from_peer(
            self,
            block_hash: Hash32,
            address: Address,
            peer: LESPeer) -> Account:
        key = keccak(address)
        proof = await self._get_proof(peer, block_hash, account_key=b'', key=key)
        header = await self._get_block_header_by_hash(peer, block_hash)
        try:
            rlp_account = HexaryTrie.get_from_proof(header.state_root, key, proof)
        except BadTrieProof as exc:
            raise BadLESResponse("Peer %s returned an invalid proof for account %s at block %s" % (
                peer,
                encode_hex(address),
                encode_hex(block_hash),
            )) from exc
        return rlp.decode(rlp_account, sedes=Account)

    @alru_cache(maxsize=1024, cache_exceptions=False)
    @service_timeout(COMPLETION_TIMEOUT)
    async def get_contract_code(self, block_hash: Hash32, address: Address) -> bytes:
        """
        :param block_hash: find code as of the block with block_hash
        :param address: which contract to look up

        :return: bytecode of the contract, ``b''`` if no code is set

        :raise NoEligiblePeers: if no peers are available to fulfill the request
        :raise TimeoutError: if an individual request or the overall process times out
        """
        # get account for later verification, and
        # to confirm that our highest total difficulty peer has the info
        try:
            account = await self.get_account(block_hash, address)
        except HeaderNotFound as exc:
            raise NoEligiblePeers("Our best peer does not have header %s" % block_hash) from exc

        code_hash = account.code_hash

        return await self._retry_on_bad_response(
            partial(self._get_contract_code_from_peer, block_hash, address, code_hash)
        )

    async def _get_contract_code_from_peer(
            self,
            block_hash: Hash32,
            address: Address,
            code_hash: Hash32,
            peer: LESPeer) -> bytes:
        """
        A single attempt to get the contract code from the given peer

        :raise BadLESResponse: if the peer replies with contract code that does not match the
            account's code hash
        """
        # request contract code
        request_id = gen_request_id()
        peer.sub_proto.send_get_contract_code(block_hash, keccak(address), request_id)
        reply = await self._wait_for_reply(request_id)

        if not reply['codes']:
            bytecode = b''
        else:
            bytecode = reply['codes'][0]

        # validate bytecode against a proven account
        if code_hash == keccak(bytecode):
            return bytecode
        elif bytecode == b'':
            # TODO disambiguate failure types here, and raise the appropriate exception
            # An (incorrectly) empty bytecode might indicate a bad-acting peer, or it might not
            raise NoEligiblePeers("Our best peer incorrectly responded with an empty code value")
        else:
            # a bad-acting peer sent an invalid non-empty bytecode
            raise BadLESResponse("Peer %s sent code %s that did not match hash %s in account %s" % (
                peer,
                encode_hex(bytecode),
                encode_hex(code_hash),
                encode_hex(address),
            ))

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

    async def _retry_on_bad_response(self, make_request_to_peer: Callable[[LESPeer], Any]) -> Any:
        for _ in range(MAX_REQUEST_ATTEMPTS):
            peer = cast(LESPeer, self.peer_pool.highest_td_peer)
            try:
                return await make_request_to_peer(peer)
            except BadLESResponse as exc:
                self.logger.warn("Disconnecting from peer, because: %s", exc)
                await peer.disconnect(DisconnectReason.subprotocol_error)
                # reattempt after removing this peer from our pool

        raise TimeoutError("Could not complete peer request in %d attempts" % MAX_REQUEST_ATTEMPTS)
