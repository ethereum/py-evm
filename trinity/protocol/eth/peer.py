import asyncio
from typing import (
    Any,
    cast,
    Dict,
    Tuple,
)

from eth_utils import encode_hex

from eth_typing import BlockIdentifier

from eth.rlp.headers import BlockHeader

from p2p.exceptions import HandshakeFailure
from p2p.p2p_proto import DisconnectReason
from p2p.peer import BasePeer
from p2p.protocol import (
    Command,
    _DecodedMsgType,
)

from trinity.protocol.base_request import BaseRequest
from .commands import (
    BlockHeaders,
    NewBlock,
    Status,
)
from . import constants
from .requests import HeaderRequest
from .proto import ETHProtocol


class ETHPeer(BasePeer):
    _supported_sub_protocols = [ETHProtocol]
    sub_proto: ETHProtocol = None

    @property
    def max_headers_fetch(self) -> int:
        return constants.MAX_HEADERS_FETCH

    def handle_sub_proto_msg(self, cmd: Command, msg: _DecodedMsgType) -> None:
        if isinstance(cmd, NewBlock):
            msg = cast(Dict[str, Any], msg)
            header, _, _ = msg['block']
            actual_head = header.parent_hash
            actual_td = msg['total_difficulty'] - header.difficulty
            if actual_td > self.head_td:
                self.head_hash = actual_head
                self.head_td = actual_td

        super().handle_sub_proto_msg(cmd, msg)

    async def send_sub_proto_handshake(self) -> None:
        self.sub_proto.send_handshake(await self._local_chain_info)

    async def process_sub_proto_handshake(
            self, cmd: Command, msg: _DecodedMsgType) -> None:
        if not isinstance(cmd, Status):
            await self.disconnect(DisconnectReason.subprotocol_error)
            raise HandshakeFailure(
                "Expected a ETH Status msg, got {}, disconnecting".format(cmd))
        msg = cast(Dict[str, Any], msg)
        if msg['network_id'] != self.network_id:
            await self.disconnect(DisconnectReason.useless_peer)
            raise HandshakeFailure(
                "{} network ({}) does not match ours ({}), disconnecting".format(
                    self, msg['network_id'], self.network_id))
        genesis = await self.genesis
        if msg['genesis_hash'] != genesis.hash:
            await self.disconnect(DisconnectReason.useless_peer)
            raise HandshakeFailure(
                "{} genesis ({}) does not match ours ({}), disconnecting".format(
                    self, encode_hex(msg['genesis_hash']), genesis.hex_hash))
        self.head_td = msg['td']
        self.head_hash = msg['best_hash']

    def request_block_headers(self,
                              block_number_or_hash: BlockIdentifier,
                              max_headers: int = None,
                              skip: int = 0,
                              reverse: bool = True) -> HeaderRequest:
        if max_headers is None:
            max_headers = self.max_headers_fetch
        request = HeaderRequest(
            block_number_or_hash,
            max_headers,
            skip,
            reverse,
        )
        self.sub_proto.send_get_block_headers(
            request.block_number_or_hash,
            request.max_headers,
            request.skip,
            request.reverse,
        )
        return request

    async def wait_for_block_headers(self, request: HeaderRequest) -> Tuple[BlockHeader, ...]:
        future: 'asyncio.Future[Tuple[BlockHeader, ...]]' = asyncio.Future()
        self.pending_requests[BlockHeaders] = cast(
            Tuple[BaseRequest, 'asyncio.Future[_DecodedMsgType]'],
            (request, future),
        )
        response = await self.wait(future, timeout=self._response_timeout)
        return response

    async def get_block_headers(self,
                                block_number_or_hash: BlockIdentifier,
                                max_headers: int = None,
                                skip: int = 0,
                                reverse: bool = True) -> Tuple[BlockHeader, ...]:
        request = self.request_block_headers(block_number_or_hash, max_headers, skip, reverse)
        return await self.wait_for_block_headers(request)
