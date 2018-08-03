from typing import (
    Any,
    cast,
    Dict,
)

from eth_utils import encode_hex

from p2p.exceptions import (
    HandshakeFailure,
)
from p2p.p2p_proto import DisconnectReason
from p2p.peer import BasePeer
from p2p.protocol import (
    Command,
    _DecodedMsgType,
)

from .commands import (
    Announce,
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
from .handlers import LESRequestResponseHandler


class LESPeer(BasePeer):
    _supported_sub_protocols = [LESProtocol, LESProtocolV2]
    sub_proto: LESProtocol = None
    # TODO: This will no longer be needed once we've fixed #891, and then it should be removed.
    head_info: HeadInfo = None

    _requests: LESRequestResponseHandler = None

    @property
    def requests(self) -> LESRequestResponseHandler:
        if self._requests is None:
            self._requests = LESRequestResponseHandler(self)
            self.run_child_service(self._requests)
        return self._requests

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
