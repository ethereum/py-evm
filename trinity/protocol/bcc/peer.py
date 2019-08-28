from typing import Sequence, Tuple

from lahja import EndpointAPI

from eth2.beacon.types.blocks import (
    BeaconBlock,
)

from lahja import (
    BroadcastConfig,
)

from p2p.abc import CommandAPI, HandshakeReceiptAPI, NodeAPI
from p2p.handshake import DevP2PReceipt
from p2p.peer import (
    BasePeer,
    BasePeerFactory,
)
from p2p.peer_pool import BasePeerPool
from p2p.protocol import Payload

from trinity.protocol.bcc.handlers import BCCExchangeHandler

from trinity.protocol.bcc.proto import BCCProtocol, ProxyBCCProtocol
from trinity.protocol.bcc.commands import (
    GetBeaconBlocks,
)
from trinity.protocol.bcc.context import (
    BeaconContext,
)
from trinity.protocol.common.peer import (
    BaseProxyPeer,
)
from trinity.protocol.common.peer_pool_event_bus import (
    PeerPoolEventServer,
)

from .events import (
    GetBeaconBlocksEvent,
    SendBeaconBlocksEvent,
)
from .handshaker import (
    BCCHandshaker,
    BCCHandshakeReceipt,
)
from .proto import BCCHandshakeParams


class BCCProxyPeer(BaseProxyPeer):
    """
    A ``BCCPeer`` that can be used from any process instead of the actual peer pool peer.
    Any action performed on the ``BCCProxyPeer`` is delegated to the actual peer in the pool.
    This does not yet mimic all APIs of the real peer.
    """

    def __init__(self,
                 remote: NodeAPI,
                 event_bus: EndpointAPI,
                 sub_proto: ProxyBCCProtocol):

        super().__init__(remote, event_bus)

        self.sub_proto = sub_proto

    @classmethod
    def from_node(cls,
                  remote: NodeAPI,
                  event_bus: EndpointAPI,
                  broadcast_config: BroadcastConfig) -> 'BCCProxyPeer':
        return cls(remote, event_bus, ProxyBCCProtocol(remote, event_bus, broadcast_config))


class BCCPeer(BasePeer):
    supported_sub_protocols = (BCCProtocol,)
    sub_proto: BCCProtocol = None

    _requests: BCCExchangeHandler = None

    def process_handshake_receipts(self,
                                   devp2p_receipt: DevP2PReceipt,
                                   protocol_receipts: Sequence[HandshakeReceiptAPI]) -> None:
        super().process_handshake_receipts(devp2p_receipt, protocol_receipts)
        for receipt in protocol_receipts:
            if isinstance(receipt, BCCHandshakeReceipt):
                self.head_slot = receipt.handshake_params.head_slot
                self.genesis_root = receipt.handshake_params.genesis_root
                self.network_id = receipt.handshake_params.network_id
                break
        else:
            raise Exception(
                "Did not find an `BCCHandshakeReceipt` in {protocol_receipts}"
            )

    @property
    def requests(self) -> BCCExchangeHandler:
        if self._requests is None:
            self._requests = BCCExchangeHandler(self)
        return self._requests


class BCCPeerFactory(BasePeerFactory):
    context: BeaconContext
    peer_class = BCCPeer

    async def get_handshakers(self) -> Tuple[BCCHandshaker, ...]:
        chain_db = self.context.chain_db
        head = await chain_db.coro_get_canonical_head(BeaconBlock)
        genesis_root = await chain_db.coro_get_genesis_block_root()

        handshake_params = BCCHandshakeParams(
            head_slot=head.slot,
            genesis_root=genesis_root,
            network_id=self.context.network_id,
            protocol_version=BCCProtocol.version,
        )
        return (
            BCCHandshaker(handshake_params),
        )


class BCCPeerPool(BasePeerPool):
    peer_factory_class = BCCPeerFactory


class BCCPeerPoolEventServer(PeerPoolEventServer[BCCPeer]):
    """
    BCC protocol specific ``PeerPoolEventServer``. See ``PeerPoolEventServer`` for more info.
    """

    subscription_msg_types = frozenset({GetBeaconBlocks})

    async def _run(self) -> None:

        self.run_daemon_event(
            SendBeaconBlocksEvent,
            lambda event: self.try_with_node(
                event.remote,
                lambda peer: peer.sub_proto.send_blocks(event.blocks, event.request_id)
            )
        )

        await super()._run()

    async def handle_native_peer_message(self,
                                         remote: NodeAPI,
                                         cmd: CommandAPI,
                                         msg: Payload) -> None:

        if isinstance(cmd, GetBeaconBlocks):
            await self.event_bus.broadcast(GetBeaconBlocksEvent(remote, cmd, msg))
        else:
            raise Exception(f"Command {cmd} is not broadcasted")
