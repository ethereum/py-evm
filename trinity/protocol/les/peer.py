from typing import (
    Any,
    cast,
    Dict,
    List,
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
from .handlers import LESExchangeHandler


class LESPeer(BasePeer):
    max_headers_fetch = MAX_HEADERS_FETCH

    _supported_sub_protocols = [LESProtocol, LESProtocolV2]
    sub_proto: LESProtocol = None
    # TODO: This will no longer be needed once we've fixed #891, and then it should be removed.
    head_info: HeadInfo = None

    _requests: LESExchangeHandler = None

    def get_extra_stats(self) -> List[str]:
        stats_pairs = self.requests.get_stats().items()
        return ['%s: %s' % (cmd_name, stats) for cmd_name, stats in stats_pairs]

    @property
    def requests(self) -> LESExchangeHandler:
        if self._requests is None:
            self._requests = LESExchangeHandler(self)
        return self._requests

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
