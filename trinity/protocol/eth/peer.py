from typing import (
    Any,
    cast,
    Dict,
    List,
)

from eth_utils import encode_hex

from p2p.exceptions import (
    HandshakeFailure,
    WrongNetworkFailure,
    WrongGenesisFailure,
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
    NewBlock,
    Status,
)
from .constants import MAX_HEADERS_FETCH
from .proto import ETHProtocol
from .handlers import ETHExchangeHandler


class ETHPeer(BaseChainPeer):
    max_headers_fetch = MAX_HEADERS_FETCH

    supported_sub_protocols = (ETHProtocol,)
    sub_proto: ETHProtocol = None

    _requests: ETHExchangeHandler = None

    def get_extra_stats(self) -> List[str]:
        stats_pairs = self.requests.get_stats().items()
        return ['%s: %s' % (cmd_name, stats) for cmd_name, stats in stats_pairs]

    @property
    def requests(self) -> ETHExchangeHandler:
        if self._requests is None:
            self._requests = ETHExchangeHandler(self)
        return self._requests

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
            raise HandshakeFailure(f"Expected a ETH Status msg, got {cmd}, disconnecting")

        msg = cast(Dict[str, Any], msg)

        self.head_td = msg['td']
        self.head_hash = msg['best_hash']
        self.network_id = msg['network_id']
        self.genesis_hash = msg['genesis_hash']

        if msg['network_id'] != self.local_network_id:
            await self.disconnect(DisconnectReason.useless_peer)
            raise WrongNetworkFailure(
                f"{self} network ({msg['network_id']}) does not match ours "
                f"({self.local_network_id}), disconnecting"
            )

        local_genesis_hash = await self._get_local_genesis_hash()
        if msg['genesis_hash'] != local_genesis_hash:
            await self.disconnect(DisconnectReason.useless_peer)
            raise WrongGenesisFailure(
                f"{self} genesis ({encode_hex(msg['genesis_hash'])}) does not "
                f"match ours ({local_genesis_hash}), disconnecting"
            )


class ETHPeerFactory(BaseChainPeerFactory):
    peer_class = ETHPeer


class ETHPeerPool(BaseChainPeerPool):
    peer_factory_class = ETHPeerFactory
