from typing import (
    Any,
    cast,
    Dict,
    Tuple,
)

from eth.rlp.headers import BlockHeader
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
    BaseProxyPeer,
    BaseProxyPeerPool,
    PeerPoolEventServer,
)
from trinity.protocol.common.types import (
    BlockBodyBundles,
    NodeDataBundles,
    ReceiptsBundles,
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
    GetBlockHeadersRequest,
    GetBlockBodiesEvent,
    GetBlockBodiesRequest,
    GetReceiptsEvent,
    GetNodeDataEvent,
    GetNodeDataRequest,
    GetReceiptsRequest,
    NewBlockHashesEvent,
    SendBlockBodiesEvent,
    SendBlockHeadersEvent,
    SendNodeDataEvent,
    SendReceiptsEvent,
    TransactionsEvent,
)
from .proto import ETHProtocol, ProxyETHProtocol
from .handlers import ETHExchangeHandler, ProxyETHExchangeHandler


class ETHPeer(BaseChainPeer):
    max_headers_fetch = MAX_HEADERS_FETCH

    supported_sub_protocols = (ETHProtocol,)
    sub_proto: ETHProtocol = None

    _requests: ETHExchangeHandler = None

    def get_extra_stats(self) -> Tuple[str, ...]:
        stats_pairs = self.requests.get_stats().items()
        return tuple(
            f"{cmd_name}: {stats}" for cmd_name, stats in stats_pairs
        )

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


class ETHProxyPeer(BaseProxyPeer):
    """
    A ``ETHPeer`` that can be used from any process instead of the actual peer pool peer.
    Any action performed on the ``BCCProxyPeer`` is delegated to the actual peer in the pool.
    This does not yet mimic all APIs of the real peer.
    """

    def __init__(self,
                 remote: Node,
                 event_bus: TrinityEventBusEndpoint,
                 sub_proto: ProxyETHProtocol,
                 requests: ProxyETHExchangeHandler):

        super().__init__(remote, event_bus)

        self.sub_proto = sub_proto
        self.requests = requests

    @classmethod
    def from_node(cls,
                  remote: Node,
                  event_bus: TrinityEventBusEndpoint,
                  broadcast_config: BroadcastConfig) -> 'ETHProxyPeer':
        return cls(
            remote,
            event_bus,
            ProxyETHProtocol(remote, event_bus, broadcast_config),
            ProxyETHExchangeHandler(remote, event_bus, broadcast_config)
        )


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
        Transactions,
        NewBlockHashes,
    })

    async def _run(self) -> None:

        self.run_daemon_event(
            SendBlockHeadersEvent,
            lambda event: self.try_with_node(
                event.remote,
                lambda peer: peer.sub_proto.send_block_headers(event.headers)
            )
        )
        self.run_daemon_event(
            SendBlockBodiesEvent,
            lambda event: self.try_with_node(
                event.remote,
                lambda peer: peer.sub_proto.send_block_bodies(event.blocks)
            )
        )
        self.run_daemon_event(
            SendNodeDataEvent,
            lambda event: self.try_with_node(
                event.remote,
                lambda peer: peer.sub_proto.send_node_data(event.nodes)
            )
        )
        self.run_daemon_event(
            SendReceiptsEvent,
            lambda event: self.try_with_node(
                event.remote,
                lambda peer: peer.sub_proto.send_receipts(event.receipts)
            )
        )

        self.run_daemon_request(GetBlockHeadersRequest, self.handle_get_block_headers_request)
        self.run_daemon_request(GetReceiptsRequest, self.handle_get_receipts_request)
        self.run_daemon_request(GetBlockBodiesRequest, self.handle_get_block_bodies_request)
        self.run_daemon_request(GetNodeDataRequest, self.handle_get_node_data_request)

        await super()._run()

    async def handle_get_block_headers_request(
            self,
            event: GetBlockHeadersRequest) -> Tuple[BlockHeader, ...]:
        peer = self.get_peer(event.remote)
        return await peer.requests.get_block_headers(
            event.block_number_or_hash,
            event.max_headers,
            skip=event.skip,
            reverse=event.reverse,
            timeout=event.timeout
        )

    async def handle_get_receipts_request(self,
                                          event: GetReceiptsRequest) -> ReceiptsBundles:

        return await self.with_node_and_timeout(
            event.remote,
            event.timeout,
            lambda peer: peer.requests.get_receipts(event.headers)
        )

    async def handle_get_block_bodies_request(self,
                                              event: GetBlockBodiesRequest) -> BlockBodyBundles:
        return await self.with_node_and_timeout(
            event.remote,
            event.timeout,
            lambda peer: peer.requests.get_block_bodies(event.headers)
        )

    async def handle_get_node_data_request(self,
                                           event: GetNodeDataRequest) -> NodeDataBundles:
        return await self.with_node_and_timeout(
            event.remote,
            event.timeout,
            lambda peer: peer.requests.get_node_data(event.node_hashes)
        )

    async def handle_native_peer_message(self,
                                         remote: Node,
                                         cmd: Command,
                                         msg: PayloadType) -> None:

        if isinstance(cmd, GetBlockHeaders):
            await self.event_bus.broadcast(GetBlockHeadersEvent(remote, cmd, msg))
        elif isinstance(cmd, GetBlockBodies):
            await self.event_bus.broadcast(GetBlockBodiesEvent(remote, cmd, msg))
        elif isinstance(cmd, GetReceipts):
            await self.event_bus.broadcast(GetReceiptsEvent(remote, cmd, msg))
        elif isinstance(cmd, GetNodeData):
            await self.event_bus.broadcast(GetNodeDataEvent(remote, cmd, msg))
        elif isinstance(cmd, NewBlockHashes):
            await self.event_bus.broadcast(NewBlockHashesEvent(remote, cmd, msg))
        elif isinstance(cmd, Transactions):
            await self.event_bus.broadcast(TransactionsEvent(remote, cmd, msg))
        else:
            raise Exception(f"Command {cmd} is not broadcasted")


class ETHPeerPool(BaseChainPeerPool):
    peer_factory_class = ETHPeerFactory


class ETHProxyPeerPool(BaseProxyPeerPool[ETHProxyPeer]):

    def convert_node_to_proxy_peer(self,
                                   remote: Node,
                                   event_bus: TrinityEventBusEndpoint,
                                   broadcast_config: BroadcastConfig) -> ETHProxyPeer:
        return ETHProxyPeer.from_node(
            remote,
            self.event_bus,
            self.broadcast_config
        )
