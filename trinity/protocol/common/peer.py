from abc import abstractmethod
import operator
import random
from typing import (
    Dict,
    List,
    Tuple,
    Type,
    Union,
)

from cached_property import cached_property

from lahja import EndpointAPI

from cancel_token import CancelToken

from eth_utils.toolz import (
    excepts,
    groupby,
)

from p2p.abc import BehaviorAPI, NodeAPI, SessionAPI
from p2p.disconnect import DisconnectReason
from p2p.exceptions import (
    NoConnectedPeers,
    UnknownAPI,
)
from p2p.peer import (
    BasePeer,
    BasePeerFactory,
)
from p2p.peer_backend import (
    BasePeerBackend,
)
from p2p.peer_pool import (
    BasePeerPool,
)
from p2p.service import BaseService
from p2p.tracking.connection import (
    BaseConnectionTracker,
    NoopConnectionTracker,
)

from trinity.constants import TO_NETWORKING_BROADCAST_CONFIG
from trinity.protocol.common.abc import ChainInfoAPI, HeadInfoAPI
from trinity.protocol.common.api import ChainInfo, HeadInfo
from trinity.protocol.eth.api import ETHAPI
from trinity.protocol.les.api import LESV1API, LESV2API
from trinity.protocol.les.proto import LESProtocolV1, LESProtocolV2

from trinity.components.builtin.network_db.connection.tracker import ConnectionTrackerClient
from trinity.components.builtin.network_db.eth1_peer_db.tracker import (
    BaseEth1PeerTracker,
    EventBusEth1PeerTracker,
    NoopEth1PeerTracker,
)

from .boot import DAOCheckBootManager
from .context import ChainContext
from .events import (
    DisconnectPeerEvent,
)


class BaseChainPeer(BasePeer):
    boot_manager_class = DAOCheckBootManager
    context: ChainContext

    @cached_property
    def chain_api(self) -> Union[ETHAPI, LESV1API, LESV2API]:
        if self.connection.has_logic(ETHAPI.name):
            return self.connection.get_logic(ETHAPI.name, ETHAPI)
        elif self.connection.has_logic(LESV1API.name):
            if self.connection.has_protocol(LESProtocolV2):
                return self.connection.get_logic(LESV2API.name, LESV2API)
            elif self.connection.has_protocol(LESProtocolV1):
                return self.connection.get_logic(LESV1API.name, LESV1API)
            else:
                raise Exception("Should be unreachable")
        else:
            raise Exception("Should be unreachable")

    @cached_property
    def head_info(self) -> HeadInfoAPI:
        return self.connection.get_logic(HeadInfo.name, HeadInfo)

    @cached_property
    def chain_info(self) -> ChainInfoAPI:
        return self.connection.get_logic(ChainInfo.name, ChainInfo)

    def get_behaviors(self) -> Tuple[BehaviorAPI, ...]:
        return (
            HeadInfo().as_behavior(),
            ChainInfo().as_behavior(),
        )

    @property
    @abstractmethod
    def max_headers_fetch(self) -> int:
        ...

    def setup_connection_tracker(self) -> BaseConnectionTracker:
        if self.has_event_bus:
            return ConnectionTrackerClient(self.get_event_bus())
        else:
            self.logger.warning(
                "No event_bus set on peer.  Connection tracking falling back to "
                "`NoopConnectionTracker`."
            )
            return NoopConnectionTracker()


class BaseProxyPeer(BaseService):
    """
    Base class for peers that can be used from any process where the actual peer is not available.
    """

    def __init__(self,
                 session: SessionAPI,
                 event_bus: EndpointAPI,
                 token: CancelToken = None):

        self.event_bus = event_bus
        self.session = session
        super().__init__(token)

    def __str__(self) -> str:
        return f"{self.__class__.__name__} {self.session}"

    async def _run(self) -> None:
        self.logger.debug("Starting Proxy Peer %s", self)
        await self.cancellation()

    async def disconnect(self, reason: DisconnectReason) -> None:
        self.logger.debug("Forwarding `disconnect()` call from proxy to actual peer: %s", self)
        await self.event_bus.broadcast(
            DisconnectPeerEvent(self.session, reason),
            TO_NETWORKING_BROADCAST_CONFIG,
        )
        await self.cancel()


class BaseChainPeerFactory(BasePeerFactory):
    context: ChainContext
    peer_class: Type[BaseChainPeer]


class BaseChainPeerPool(BasePeerPool):
    connected_nodes: Dict[NodeAPI, BaseChainPeer]  # type: ignore
    peer_factory_class: Type[BaseChainPeerFactory]
    peer_tracker: BaseEth1PeerTracker

    @property
    def highest_td_peer(self) -> BaseChainPeer:
        peers = tuple(self.connected_nodes.values())
        if not peers:
            raise NoConnectedPeers("No connected peers")

        td_getter = excepts(UnknownAPI, operator.attrgetter('head_info.head_td'), lambda _: 0)
        peers_by_td = groupby(td_getter, peers)
        max_td = max(peers_by_td.keys())
        return random.choice(peers_by_td[max_td])

    def get_peers(self, min_td: int) -> List[BaseChainPeer]:
        # TODO: Consider turning this into a method that returns an AsyncIterator, to make it
        # harder for callsites to get a list of peers while making blocking calls, as those peers
        # might disconnect in the meantime.
        peers = tuple(self.connected_nodes.values())
        return [peer for peer in peers if peer.head_info.head_td >= min_td]

    def setup_connection_tracker(self) -> BaseConnectionTracker:
        if self.has_event_bus:
            return ConnectionTrackerClient(self.get_event_bus())
        else:
            return NoopConnectionTracker()

    def setup_peer_backends(self) -> Tuple[BasePeerBackend, ...]:
        if self.has_event_bus:
            self.peer_tracker = EventBusEth1PeerTracker(self.get_event_bus())
        else:
            self.peer_tracker = NoopEth1PeerTracker()

        self.subscribe(self.peer_tracker)
        return super().setup_peer_backends() + (self.peer_tracker,)
