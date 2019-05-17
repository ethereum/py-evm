from abc import ABC, abstractmethod
from typing import (
    Set,
    Tuple,
)

from lahja import (
    Endpoint,
    BroadcastConfig,
)

from p2p.constants import (
    DISCOVERY_EVENTBUS_ENDPOINT,
)
from p2p.kademlia import (
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
                                  connected_remotes: Set[Node]) -> Tuple[Node, ...]:
        pass


TO_DISCOVERY_BROADCAST_CONFIG = BroadcastConfig(filter_endpoint=DISCOVERY_EVENTBUS_ENDPOINT)


class DiscoveryPeerBackend(BasePeerBackend):
    def __init__(self, event_bus: Endpoint) -> None:
        self.event_bus = event_bus

    async def get_peer_candidates(self,
                                  num_requested: int,
                                  connected_remotes: Set[Node]) -> Tuple[Node, ...]:
        response = await self.event_bus.request(
            PeerCandidatesRequest(num_requested),
            TO_DISCOVERY_BROADCAST_CONFIG,
        )
        return tuple(
            candidate
            for candidate in response.candidates
            if candidate not in connected_remotes
        )


class BootnodesPeerBackend(BasePeerBackend):
    def __init__(self, event_bus: Endpoint) -> None:
        self.event_bus = event_bus

    async def get_peer_candidates(self,
                                  num_requested: int,
                                  connected_remotes: Set[Node]) -> Tuple[Node, ...]:
        if len(connected_remotes) == 0:
            response = await self.event_bus.request(
                RandomBootnodeRequest(),
                TO_DISCOVERY_BROADCAST_CONFIG
            )

            return tuple(
                candidate
                for candidate in response.candidates
                if candidate not in connected_remotes
            )
        else:
            return ()
