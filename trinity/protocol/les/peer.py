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

from p2p.exceptions import (
    HandshakeFailure,
)
from p2p.p2p_proto import DisconnectReason
from p2p.peer import BasePeer
from p2p.protocol import (
    Command,
    _DecodedMsgType,
)

from trinity.protocol.base_request import BaseHeaderRequest

from .commands import (
    Announce,
    BlockHeaders,
    HeadInfo,
    Status,
    StatusV2,
)
from .constants import (
    MAX_HEADERS_FETCH,
)
from .proto import (
    LESProtocol,
    LESProtocolV2,
)
from .requests import (
    HeaderRequest,
)
from .utils import (
    gen_request_id as _gen_request_id,
)


class LESPeer(BasePeer):
    _supported_sub_protocols = [LESProtocol, LESProtocolV2]
    sub_proto: LESProtocol = None
    # TODO: This will no longer be needed once we've fixed #891, and then it should be removed.
    head_info: HeadInfo = None

    @property
    def max_headers_fetch(self) -> int:
        return MAX_HEADERS_FETCH

    def handle_sub_proto_msg(self, cmd: Command, msg: _DecodedMsgType) -> None:
        if isinstance(cmd, Announce):
            self.head_info = cmd.as_head_info(msg)
            self.head_td = self.head_info.total_difficulty
            self.head_hash = self.head_info.block_hash

        super().handle_sub_proto_msg(cmd, msg)

    async def send_sub_proto_handshake(self) -> None:
        self.sub_proto.send_handshake(await self._local_chain_info)

    async def process_sub_proto_handshake(
            self, cmd: Command, msg: _DecodedMsgType) -> None:
        if not isinstance(cmd, (Status, StatusV2)):
            await self.disconnect(DisconnectReason.subprotocol_error)
            raise HandshakeFailure(
                "Expected a LES Status msg, got {}, disconnecting".format(cmd))
        msg = cast(Dict[str, Any], msg)
        if msg['networkId'] != self.network_id:
            await self.disconnect(DisconnectReason.useless_peer)
            raise HandshakeFailure(
                "{} network ({}) does not match ours ({}), disconnecting".format(
                    self, msg['networkId'], self.network_id))
        genesis = await self.genesis
        if msg['genesisHash'] != genesis.hash:
            await self.disconnect(DisconnectReason.useless_peer)
            raise HandshakeFailure(
                "{} genesis ({}) does not match ours ({}), disconnecting".format(
                    self, encode_hex(msg['genesisHash']), genesis.hex_hash))
        # TODO: Disconnect if the remote doesn't serve headers.
        self.head_info = cmd.as_head_info(msg)
        self.head_td = self.head_info.total_difficulty
        self.head_hash = self.head_info.block_hash

    def gen_request_id(self) -> int:
        return _gen_request_id()

    def request_block_headers(self,
                              block_number_or_hash: BlockIdentifier,
                              max_headers: int = None,
                              skip: int = 0,
                              reverse: bool = False) -> HeaderRequest:
        if max_headers is None:
            max_headers = self.max_headers_fetch
        request_id = self.gen_request_id()
        request = HeaderRequest(
            block_number_or_hash,
            max_headers,
            skip,
            reverse,
            request_id,
        )
        self.sub_proto.send_get_block_headers(
            request.block_number_or_hash,
            request.max_headers,
            request.skip,
            request.reverse,
            request_id,
        )
        return request

    async def wait_for_block_headers(self, request: HeaderRequest) -> Tuple[BlockHeader, ...]:
        future: 'asyncio.Future[_DecodedMsgType]' = asyncio.Future()
        if BlockHeaders in self.pending_requests:
            # the `finally` block below should prevent this from happening, but
            # were two requests to the same peer to be fired off at the same
            # time, this will prevent us from overwriting the first one.
            raise ValueError(
                "There is already a pending `BlockHeaders` request for peer {0}".format(self)
            )
        self.pending_requests[BlockHeaders] = cast(
            Tuple[BaseHeaderRequest, 'asyncio.Future[_DecodedMsgType]'],
            (request, future),
        )
        try:
            response = cast(
                Dict[str, Any],
                await self.wait(future, timeout=self._response_timeout),
            )
        finally:
            # We always want to be sure that this method cleans up the
            # `pending_requests` so that we don't end up in a situation.
            self.pending_requests.pop(BlockHeaders, None)
        return cast(Tuple[BlockHeader, ...], response['headers'])

    async def get_block_headers(self,
                                block_number_or_hash: BlockIdentifier,
                                max_headers: int = None,
                                skip: int = 0,
                                reverse: bool = True) -> Tuple[BlockHeader, ...]:
        request = self.request_block_headers(block_number_or_hash, max_headers, skip, reverse)
        return await self.wait_for_block_headers(request)
