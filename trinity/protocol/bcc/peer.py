from typing import (
    cast,
)

from eth_utils import (
    encode_hex,
)
from eth_typing import (
    Hash32,
)

from trinity.db.beacon.chain import BaseAsyncBeaconChainDB
from eth2.beacon.types.blocks import (
    BeaconBlock,
)

from eth2.beacon.typing import (
    Slot,
)
from lahja import (
    BroadcastConfig,
)

from p2p.peer import (
    BasePeer,
    BasePeerFactory,
)
from p2p.peer_pool import (
    BasePeerPool,
)
from p2p.protocol import (
    Command,
    _DecodedMsgType,
    PayloadType,
)
from p2p.exceptions import HandshakeFailure
from p2p.kademlia import Node
from p2p.p2p_proto import DisconnectReason

from trinity.endpoint import TrinityEventBusEndpoint
from trinity.protocol.bcc.handlers import BCCExchangeHandler

from trinity.protocol.bcc.proto import BCCProtocol, ProxyBCCProtocol
from trinity.protocol.bcc.commands import (
    GetBeaconBlocks,
    Status,
    StatusMessage,
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


class BCCProxyPeer(BaseProxyPeer):
    """
    A ``BCCPeer`` that can be used from any process instead of the actual peer pool peer.
    Any action performed on the ``BCCProxyPeer`` is delegated to the actual peer in the pool.
    This does not yet mimic all APIs of the real peer.
    """

    def __init__(self,
                 remote: Node,
                 event_bus: TrinityEventBusEndpoint,
                 sub_proto: ProxyBCCProtocol):

        super().__init__(remote, event_bus)

        self.sub_proto = sub_proto

    @classmethod
    def from_node(cls,
                  remote: Node,
                  event_bus: TrinityEventBusEndpoint,
                  broadcast_config: BroadcastConfig) -> 'BCCProxyPeer':
        return cls(remote, event_bus, ProxyBCCProtocol(remote, event_bus, broadcast_config))


class BCCPeer(BasePeer):

    supported_sub_protocols = (BCCProtocol,)
    sub_proto: BCCProtocol = None

    _requests: BCCExchangeHandler = None

    context: BeaconContext

    head_slot: Slot = None

    _genesis_root: Hash32 = None

    async def send_sub_proto_handshake(self) -> None:
        genesis_root = await self.get_genesis_root()
        head = await self.chain_db.coro_get_canonical_head(BeaconBlock)
        self.sub_proto.send_handshake(genesis_root, head.slot, self.network_id)

    async def process_sub_proto_handshake(self, cmd: Command, msg: _DecodedMsgType) -> None:
        if not isinstance(cmd, Status):
            await self.disconnect(DisconnectReason.subprotocol_error)
            raise HandshakeFailure(f"Expected a BCC Status msg, got {cmd}, disconnecting")

        msg = cast(StatusMessage, msg)
        if msg['network_id'] != self.network_id:
            await self.disconnect(DisconnectReason.useless_peer)
            raise HandshakeFailure(
                f"{self} network ({msg['network_id']}) does not match ours "
                f"({self.network_id}), disconnecting"
            )
        genesis_root = await self.get_genesis_root()

        if msg['genesis_root'] != genesis_root:
            await self.disconnect(DisconnectReason.useless_peer)
            raise HandshakeFailure(
                f"{self} genesis ({encode_hex(msg['genesis_root'])}) does not "
                f"match ours ({encode_hex(genesis_root)}), disconnecting"
            )

        self.head_slot = msg['head_slot']

    async def get_genesis_root(self) -> Hash32:
        if self._genesis_root is None:
            self._genesis_root = await self.chain_db.coro_get_genesis_block_root()
        return self._genesis_root

    @property
    def network_id(self) -> int:
        return self.context.network_id

    @property
    def chain_db(self) -> BaseAsyncBeaconChainDB:
        return self.context.chain_db

    @property
    def requests(self) -> BCCExchangeHandler:
        if self._requests is None:
            self._requests = BCCExchangeHandler(self)
        return self._requests


class BCCPeerFactory(BasePeerFactory):
    context: BeaconContext
    peer_class = BCCPeer


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
                                         remote: Node,
                                         cmd: Command,
                                         msg: PayloadType) -> None:

        if isinstance(cmd, GetBeaconBlocks):
            await self.event_bus.broadcast(GetBeaconBlocksEvent(remote, cmd, msg))
        else:
            raise Exception(f"Command {cmd} is not broadcasted")
