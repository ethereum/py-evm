from dataclasses import (
    dataclass,
)
from typing import (
    Tuple,
    Type,
)

from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
)

from .kademlia import Node


class BaseDiscoveryServiceResponse(BaseEvent):
    pass


@dataclass
class PeerCandidatesResponse(BaseDiscoveryServiceResponse):

    candidates: Tuple[Node, ...]


@dataclass
class PeerCandidatesRequest(BaseRequestResponseEvent[PeerCandidatesResponse]):

    max_candidates: int

    @staticmethod
    def expected_response_type() -> Type[PeerCandidatesResponse]:
        return PeerCandidatesResponse


class RandomBootnodeRequest(BaseRequestResponseEvent[PeerCandidatesResponse]):

    @staticmethod
    def expected_response_type() -> Type[PeerCandidatesResponse]:
        return PeerCandidatesResponse
