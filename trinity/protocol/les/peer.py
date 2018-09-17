from typing import (
    Any,
    cast,
    Dict,
    List,
    Union,
)

from eth_typing import (
    BlockNumber,
    Hash32,
)

from eth_utils import encode_hex

from p2p.exceptions import (
    HandshakeFailure,
)
from p2p.p2p_proto import DisconnectReason
from p2p.protocol import (
    Command,
    _DecodedMsgType,
)

from trinity.protocol.common.peer import (
    BaseChainPeer,
    BaseChainPeerFactory,
    BaseChainPeerPool,
)

from .commands import (
    Announce,
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


class LESPeer(BaseChainPeer):
    head_number: BlockNumber = None

    max_headers_fetch = MAX_HEADERS_FETCH

    _supported_sub_protocols = [LESProtocol, LESProtocolV2]
    sub_proto: LESProtocol = None

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
        head_info = cast(Dict[str, Union[int, Hash32, BlockNumber]], msg)
        if isinstance(cmd, Announce):
            self.head_td = head_info['head_td']
            self.head_hash = head_info['head_hash']
            self.head_number = head_info['head_number']

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
        # Eventually we might want to keep connections to peers where we are the only side serving
        # data, but right now both our chain syncer and the Peer.boot() method expect the remote
        # to reply to header requests, so if they don't we simply disconnect here.
        if 'serveHeaders' not in msg:
            await self.disconnect(DisconnectReason.useless_peer)
            raise HandshakeFailure(f"{self} doesn't serve headers, disconnecting")
        self.head_td = msg['headTd']
        self.head_hash = msg['headHash']
        self.head_number = msg['headNum']


class LESPeerFactory(BaseChainPeerFactory):
    peer_class = LESPeer


class LESPeerPool(BaseChainPeerPool):
    peer_factory_class = LESPeerFactory
