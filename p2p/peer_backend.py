from abc import ABC, abstractmethod
from typing import (
    Iterable,
)

from lahja import (
    Endpoint,
    BroadcastConfig,
)

from p2p.constants import (
    DISCOVERY_EVENTBUS_ENDPOINT,
)
from p2p.kademlia import (
    from_uris,
    Node,
)
from p2p.events import (
    PeerCandidatesRequest,
    RandomBootnodeRequest,
)


class BasePeerBackend(ABC):
    @abstractmethod
    async def get_peer_candidates(self,
                                  num_requested: int,
                                  num_connected_peers: int) -> Iterable[Node]:
        pass


TO_DISCOVERY_BROADCAST_CONFIG = BroadcastConfig(filter_endpoint=DISCOVERY_EVENTBUS_ENDPOINT)


class DiscoveryPeerBackend(BasePeerBackend):
    def __init__(self, event_bus: Endpoint) -> None:
        self.event_bus = event_bus

    async def get_peer_candidates(self,
                                  num_requested: int,
                                  num_connected_peers: int) -> Iterable[Node]:
        response = await self.event_bus.request(
            PeerCandidatesRequest(num_requested),
            TO_DISCOVERY_BROADCAST_CONFIG,
        )
        return from_uris(response.candidates)


class BootnodesPeerBackend(BasePeerBackend):
    def __init__(self, event_bus: Endpoint) -> None:
        self.event_bus = event_bus

    async def get_peer_candidates(self,
                                  num_requested: int,
                                  num_connected_peers: int) -> Iterable[Node]:
        if num_connected_peers == 0:
            response = await self.event_bus.request(
                RandomBootnodeRequest(),
                TO_DISCOVERY_BROADCAST_CONFIG
            )

            return from_uris(response.candidates)
        else:
            return ()
