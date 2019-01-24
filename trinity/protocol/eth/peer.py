from typing import (
    Any,
    cast,
    Dict,
    List,
)

from eth_utils import encode_hex
from lahja import (
    BroadcastConfig,
)
from p2p.exceptions import (
    HandshakeFailure,
)
from p2p.kademlia import (
    Node,
)
from p2p.p2p_proto import DisconnectReason
from p2p.protocol import (
    Command,
    _DecodedMsgType,
    PayloadType,
)

from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.exceptions import (
    WrongNetworkFailure,
    WrongGenesisFailure,
)
from trinity.protocol.common.peer import (
    BaseChainPeer,
    BaseChainPeerFactory,
    BaseChainPeerPool,
)
from trinity.protocol.common.peer_pool_event_bus import (
    PeerPoolEventServer,
)

from .commands import (
    GetBlockHeaders,
    GetBlockBodies,
    GetReceipts,
    GetNodeData,
    NewBlock,
    NewBlockHashes,
    Status,
    Transactions,
)
from .constants import MAX_HEADERS_FETCH
from .events import (
    GetBlockHeadersEvent,
    GetBlockBodiesEvent,
    GetReceiptsEvent,
    GetNodeDataEvent,
    SendBlockBodiesEvent,
    SendBlockHeadersEvent,
    SendNodeDataEvent,
    SendReceiptsEvent,
)
from .proto import ETHProtocol, ProxyETHProtocol
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


class ETHProxyPeer:
    """
    A ``ETHPeer`` that can be used from any process instead of the actual peer pool peer.
    Any action performed on the ``BCCProxyPeer`` is delegated to the actual peer in the pool.
    This does not yet mimic all APIs of the real peer.
    """

    def __init__(self, sub_proto: ProxyETHProtocol):
        self.sub_proto = sub_proto

    @classmethod
    def from_node(cls,
                  remote: Node,
                  event_bus: TrinityEventBusEndpoint,
                  broadcast_config: BroadcastConfig) -> 'ETHProxyPeer':
        return cls(ProxyETHProtocol(remote, event_bus, broadcast_config))


class ETHPeerFactory(BaseChainPeerFactory):
    peer_class = ETHPeer


class ETHPeerPoolEventServer(PeerPoolEventServer[ETHPeer]):
    """
    ETH protocol specific ``PeerPoolEventServer``. See ``PeerPoolEventServer`` for more info.
    """

    subscription_msg_types = frozenset({
        GetBlockHeaders,
        GetBlockBodies,
        GetReceipts,
        GetNodeData,
        # TODO: all of the following are here to quiet warning logging output
        # until the messages are properly handled.
        Transactions,
        NewBlockHashes,
    })

    async def _run(self) -> None:

        self.run_daemon_event(
            SendBlockHeadersEvent, lambda peer, ev: peer.sub_proto.send_block_headers(ev.headers))
        self.run_daemon_event(
            SendBlockBodiesEvent, lambda peer, ev: peer.sub_proto.send_block_bodies(ev.blocks))
        self.run_daemon_event(
            SendNodeDataEvent, lambda peer, ev: peer.sub_proto.send_node_data(ev.nodes))
        self.run_daemon_event(
            SendReceiptsEvent, lambda peer, ev: peer.sub_proto.send_receipts(ev.receipts))

        await super()._run()

    async def handle_native_peer_message(self,
                                         remote: Node,
                                         cmd: Command,
                                         msg: PayloadType) -> None:

        ignored_commands = (
            Transactions,
            NewBlockHashes,
        )

        if isinstance(cmd, ignored_commands):
            pass
        elif isinstance(cmd, GetBlockHeaders):
            await self.event_bus.broadcast(GetBlockHeadersEvent(remote, cmd, msg))
        elif isinstance(cmd, GetBlockBodies):
            await self.event_bus.broadcast(GetBlockBodiesEvent(remote, cmd, msg))
        elif isinstance(cmd, GetReceipts):
            await self.event_bus.broadcast(GetReceiptsEvent(remote, cmd, msg))
        elif isinstance(cmd, GetNodeData):
            await self.event_bus.broadcast(GetNodeDataEvent(remote, cmd, msg))
        else:
            raise Exception(f"Command {cmd} is not broadcasted")


class ETHPeerPool(BaseChainPeerPool):
    peer_factory_class = ETHPeerFactory
