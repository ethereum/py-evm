from typing import (
    Any,
    cast,
    Dict,
    List,
    Tuple,
    Union,
    TYPE_CHECKING,
)

from cancel_token import CancelToken
from eth.rlp.accounts import Account
from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt
from eth_typing import (
    BlockNumber,
    Hash32,
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
from p2p.peer_pool import BasePeerPool
from p2p.p2p_proto import DisconnectReason
from p2p.protocol import (
    Command,
    _DecodedMsgType,
    PayloadType,
)

from trinity.rlp.block_body import BlockBody
from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.exceptions import (
    WrongNetworkFailure,
    WrongGenesisFailure,
)
from trinity.protocol.common.peer import (
    BaseChainPeer,
    BaseProxyPeer,
    BaseChainPeerFactory,
    BaseChainPeerPool,
)
from trinity.protocol.common.peer_pool_event_bus import (
    PeerPoolEventServer,
    BaseProxyPeerPool,
)

from .commands import (
    Announce,
    GetBlockHeaders,
    Status,
    StatusV2,
)
from .constants import (
    MAX_HEADERS_FETCH,
)
from .events import (
    GetBlockHeadersEvent,
    SendBlockHeadersEvent,
)
from .proto import (
    LESProtocol,
    LESProtocolV2,
    ProxyLESProtocol,
)
from .events import (
    GetAccountRequest,
    GetBlockBodyByHashRequest,
    GetBlockHeaderByHashRequest,
    GetContractCodeRequest,
    GetReceiptsRequest,
)
from .handlers import LESExchangeHandler

if TYPE_CHECKING:
    from trinity.sync.light.service import BaseLightPeerChain  # noqa: F401


class LESPeer(BaseChainPeer):
    max_headers_fetch = MAX_HEADERS_FETCH

    supported_sub_protocols = (LESProtocol, LESProtocolV2)
    sub_proto: LESProtocol = None

    _requests: LESExchangeHandler = None

    def get_extra_stats(self) -> Tuple[str, ...]:
        stats_pairs = self.requests.get_stats().items()
        return tuple(
            f"{cmd_name}: {stats}" for cmd_name, stats in stats_pairs
        )

    @property
    def requests(self) -> LESExchangeHandler:
        if self._requests is None:
            self._requests = LESExchangeHandler(self)
        return self._requests

    def handle_sub_proto_msg(self, cmd: Command, msg: _DecodedMsgType) -> None:
        head_info = cast(Dict[str, Union[int, Hash32, BlockNumber]], msg)
        if isinstance(cmd, Announce):
            self.head_td = cast(int, head_info['head_td'])
            self.head_hash = cast(Hash32, head_info['head_hash'])
            self.head_number = cast(BlockNumber, head_info['head_number'])

        super().handle_sub_proto_msg(cmd, msg)

    async def send_sub_proto_handshake(self) -> None:
        self.sub_proto.send_handshake(await self._local_chain_info)

    async def process_sub_proto_handshake(
            self, cmd: Command, msg: _DecodedMsgType) -> None:
        if not isinstance(cmd, (Status, StatusV2)):
            await self.disconnect(DisconnectReason.subprotocol_error)
            raise HandshakeFailure(f"Expected a LES Status msg, got {cmd}, disconnecting")

        msg = cast(Dict[str, Any], msg)

        self.head_td = msg['headTd']
        self.head_hash = msg['headHash']
        self.head_number = msg['headNum']
        self.network_id = msg['networkId']
        self.genesis_hash = msg['genesisHash']

        if msg['networkId'] != self.local_network_id:
            await self.disconnect(DisconnectReason.useless_peer)
            raise WrongNetworkFailure(
                f"{self} network ({msg['networkId']}) does not match ours "
                f"({self.local_network_id}), disconnecting"
            )

        local_genesis_hash = await self._get_local_genesis_hash()
        if msg['genesisHash'] != local_genesis_hash:
            await self.disconnect(DisconnectReason.useless_peer)
            raise WrongGenesisFailure(
                f"{self} genesis ({encode_hex(msg['genesisHash'])}) does not "
                f"match ours ({local_genesis_hash}), disconnecting"
            )

        # Eventually we might want to keep connections to peers where we are the only side serving
        # data, but right now both our chain syncer and the Peer.boot() method expect the remote
        # to reply to header requests, so if they don't we simply disconnect here.
        if 'serveHeaders' not in msg:
            await self.disconnect(DisconnectReason.useless_peer)
            raise HandshakeFailure(f"{self} doesn't serve headers, disconnecting")


class LESProxyPeer(BaseProxyPeer):
    """
    A ``LESPeer`` that can be used from any process instead of the actual peer pool peer.
    Any action performed on the ``BCCProxyPeer`` is delegated to the actual peer in the pool.
    This does not yet mimic all APIs of the real peer.
    """

    def __init__(self,
                 remote: Node,
                 event_bus: TrinityEventBusEndpoint,
                 sub_proto: ProxyLESProtocol):

        super().__init__(remote, event_bus)

        self.sub_proto = sub_proto

    @classmethod
    def from_node(cls,
                  remote: Node,
                  event_bus: TrinityEventBusEndpoint,
                  broadcast_config: BroadcastConfig) -> 'LESProxyPeer':
        return cls(remote, event_bus, ProxyLESProtocol(remote, event_bus, broadcast_config))


class LESPeerFactory(BaseChainPeerFactory):
    peer_class = LESPeer


class LESPeerPoolEventServer(PeerPoolEventServer[LESPeer]):
    """
    LES protocol specific ``PeerPoolEventServer``. See ``PeerPoolEventServer`` for more info.
    """

    def __init__(self,
                 event_bus: TrinityEventBusEndpoint,
                 peer_pool: BasePeerPool,
                 token: CancelToken = None,
                 chain: 'BaseLightPeerChain' = None) -> None:
        super().__init__(event_bus, peer_pool, token)
        self.chain = chain

    subscription_msg_types = frozenset({GetBlockHeaders})

    async def _run(self) -> None:

        self.run_daemon_event(
            SendBlockHeadersEvent,
            lambda ev: self.try_with_node(
                ev.remote,
                lambda peer: peer.sub_proto.send_block_headers(ev.headers, ev.buffer_value, ev.request_id)  # noqa: E501
            )
        )

        self.run_daemon_request(
            GetBlockHeaderByHashRequest,
            self.handle_get_blockheader_by_hash_requests
        )
        self.run_daemon_request(
            GetBlockBodyByHashRequest,
            self.handle_get_blockbody_by_hash_requests
        )
        self.run_daemon_request(GetReceiptsRequest, self.handle_get_receipts_by_hash_requests)
        self.run_daemon_request(GetAccountRequest, self.handle_get_account_requests)
        self.run_daemon_request(GetContractCodeRequest, self.handle_get_contract_code_requests)

        await super()._run()

    async def handle_get_blockheader_by_hash_requests(
            self,
            event: GetBlockHeaderByHashRequest) -> BlockHeader:

        return await self.chain.coro_get_block_header_by_hash(event.block_hash)

    async def handle_get_blockbody_by_hash_requests(
            self,
            event: GetBlockBodyByHashRequest) -> BlockBody:

        return await self.chain.coro_get_block_body_by_hash(event.block_hash)

    async def handle_get_receipts_by_hash_requests(
            self,
            event: GetReceiptsRequest) -> List[Receipt]:

        return await self.chain.coro_get_receipts(event.block_hash)

    async def handle_get_account_requests(
            self,
            event: GetAccountRequest) -> Account:

        return await self.chain.coro_get_account(event.block_hash, event.address)

    async def handle_get_contract_code_requests(
            self,
            event: GetContractCodeRequest) -> bytes:

        return await self.chain.coro_get_contract_code(event.block_hash, event.address)

    async def handle_native_peer_message(self,
                                         remote: Node,
                                         cmd: Command,
                                         msg: PayloadType) -> None:
        if isinstance(cmd, GetBlockHeaders):
            await self.event_bus.broadcast(GetBlockHeadersEvent(remote, cmd, msg))
        else:
            raise Exception(f"Command {cmd} is not broadcasted")


class LESPeerPool(BaseChainPeerPool):
    peer_factory_class = LESPeerFactory


class LESProxyPeerPool(BaseProxyPeerPool[LESProxyPeer]):

    def convert_node_to_proxy_peer(self,
                                   remote: Node,
                                   event_bus: TrinityEventBusEndpoint,
                                   broadcast_config: BroadcastConfig) -> LESProxyPeer:
        return LESProxyPeer.from_node(
            remote,
            self.event_bus,
            self.broadcast_config
        )
