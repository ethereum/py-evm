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


class PeerCandidatesResponse(BaseDiscoveryServiceResponse):

    def __init__(self, candidates: Tuple[Node, ...]) -> None:
        self.candidates = candidates


class PeerCandidatesRequest(BaseRequestResponseEvent[PeerCandidatesResponse]):

    def __init__(self, max_candidates: int) -> None:
        self.max_candidates = max_candidates

    @staticmethod
    def expected_response_type() -> Type[PeerCandidatesResponse]:
        return PeerCandidatesResponse


class RandomBootnodeRequest(BaseRequestResponseEvent[PeerCandidatesResponse]):

    @staticmethod
    def expected_response_type() -> Type[PeerCandidatesResponse]:
        return PeerCandidatesResponse
