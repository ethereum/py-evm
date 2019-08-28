from typing import (
    cast,
    Dict,
    List,
    Sequence,
    Tuple,
    Union,
    TYPE_CHECKING,
)

from cancel_token import CancelToken
from eth.rlp.accounts import Account
from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt
from lahja import EndpointAPI

from eth_typing import (
    BlockNumber,
    Hash32,
)

from eth.constants import GENESIS_BLOCK_NUMBER

from lahja import (
    BroadcastConfig,
)

from p2p.abc import CommandAPI, ConnectionAPI, HandshakeReceiptAPI, NodeAPI
from p2p.handshake import DevP2PReceipt, Handshaker
from p2p.peer_pool import BasePeerPool
from p2p.typing import Payload

from trinity.rlp.block_body import BlockBody
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
)
from .constants import (
    MAX_HEADERS_FETCH,
)
from .events import (
    GetBlockHeadersEvent,
    SendBlockHeadersEvent,
)
from .proto import (
    LESHandshakeParams,
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
from .handshaker import LESV1Handshaker, LESV2Handshaker, LESHandshakeReceipt

if TYPE_CHECKING:
    from trinity.sync.light.service import BaseLightPeerChain  # noqa: F401


class LESPeer(BaseChainPeer):
    max_headers_fetch = MAX_HEADERS_FETCH

    supported_sub_protocols = (LESProtocol, LESProtocolV2)
    sub_proto: LESProtocol = None

    _requests: LESExchangeHandler = None

    def process_handshake_receipts(self,
                                   devp2p_receipt: DevP2PReceipt,
                                   protocol_receipts: Sequence[HandshakeReceiptAPI]) -> None:
        super().process_handshake_receipts(devp2p_receipt, protocol_receipts)
        for receipt in protocol_receipts:
            if isinstance(receipt, LESHandshakeReceipt):
                self.head_td = receipt.handshake_params.head_td
                self.head_hash = receipt.handshake_params.head_hash
                self.head_number = receipt.handshake_params.head_num
                self.genesis_hash = receipt.handshake_params.genesis_hash
                self.network_id = receipt.handshake_params.network_id
                break
        else:
            raise Exception(
                "Did not find an `LES` in {protocol_receipts}"
            )

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

    def setup_protocol_handlers(self) -> None:
        self.connection.add_command_handler(Announce, self._handle_announce)

    async def _handle_announce(self, connection: ConnectionAPI, msg: Payload) -> None:
        head_info = cast(Dict[str, Union[int, Hash32, BlockNumber]], msg)
        self.head_td = cast(int, head_info['head_td'])
        self.head_hash = cast(Hash32, head_info['head_hash'])
        self.head_number = cast(BlockNumber, head_info['head_number'])


class LESProxyPeer(BaseProxyPeer):
    """
    A ``LESPeer`` that can be used from any process instead of the actual peer pool peer.
    Any action performed on the ``BCCProxyPeer`` is delegated to the actual peer in the pool.
    This does not yet mimic all APIs of the real peer.
    """

    def __init__(self,
                 remote: NodeAPI,
                 event_bus: EndpointAPI,
                 sub_proto: ProxyLESProtocol):

        super().__init__(remote, event_bus)

        self.sub_proto = sub_proto

    @classmethod
    def from_node(cls,
                  remote: NodeAPI,
                  event_bus: EndpointAPI,
                  broadcast_config: BroadcastConfig) -> 'LESProxyPeer':
        return cls(remote, event_bus, ProxyLESProtocol(remote, event_bus, broadcast_config))


class LESPeerFactory(BaseChainPeerFactory):
    peer_class = LESPeer

    async def get_handshakers(self) -> Tuple[Handshaker, ...]:
        headerdb = self.context.headerdb
        wait = self.cancel_token.cancellable_wait

        head = await wait(headerdb.coro_get_canonical_head())
        total_difficulty = await wait(headerdb.coro_get_score(head.hash))
        genesis_hash = await wait(
            headerdb.coro_get_canonical_block_hash(BlockNumber(GENESIS_BLOCK_NUMBER))
        )
        handshake_params_kwargs = dict(
            network_id=self.context.network_id,
            head_td=total_difficulty,
            head_hash=head.hash,
            head_num=head.block_number,
            genesis_hash=genesis_hash,
            serve_headers=True,
            # TODO: these should be configurable to allow us to serve this data.
            serve_chain_since=None,
            serve_state_since=None,
            serve_recent_state=None,
            serve_recent_chain=None,
            tx_relay=None,
            flow_control_bl=None,
            flow_control_mcr=None,
            flow_control_mrr=None,
            announce_type=None,
        )
        v1_handshake_params = LESHandshakeParams(version=1, **handshake_params_kwargs)
        v2_handshake_params = LESHandshakeParams(version=2, **handshake_params_kwargs)

        return (
            LESV1Handshaker(handshake_params=v1_handshake_params),
            LESV2Handshaker(handshake_params=v2_handshake_params),
        )


class LESPeerPoolEventServer(PeerPoolEventServer[LESPeer]):
    """
    LES protocol specific ``PeerPoolEventServer``. See ``PeerPoolEventServer`` for more info.
    """

    def __init__(self,
                 event_bus: EndpointAPI,
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
                                         remote: NodeAPI,
                                         cmd: CommandAPI,
                                         msg: Payload) -> None:
        if isinstance(cmd, GetBlockHeaders):
            await self.event_bus.broadcast(GetBlockHeadersEvent(remote, cmd, msg))
        else:
            raise Exception(f"Command {cmd} is not broadcasted")


class LESPeerPool(BaseChainPeerPool):
    peer_factory_class = LESPeerFactory


class LESProxyPeerPool(BaseProxyPeerPool[LESProxyPeer]):

    def convert_node_to_proxy_peer(self,
                                   remote: NodeAPI,
                                   event_bus: EndpointAPI,
                                   broadcast_config: BroadcastConfig) -> LESProxyPeer:
        return LESProxyPeer.from_node(
            remote,
            self.event_bus,
            self.broadcast_config
        )
