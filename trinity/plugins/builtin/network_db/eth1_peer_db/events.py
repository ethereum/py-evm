from dataclasses import (
    dataclass,
)
import datetime
from typing import Optional, Set, Type, Tuple

from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
)

from eth_typing import Hash32

from p2p.kademlia import Node


class BasePeerDBEvent(BaseEvent):
    pass


@dataclass
class TrackPeerEvent(BasePeerDBEvent):

    remote: Node
    is_outbound: bool
    last_connected_at: Optional[datetime.datetime]
    genesis_hash: Hash32
    protocol: str
    protocol_version: int
    network_id: int


@dataclass
class GetPeerCandidatesResponse(BasePeerDBEvent):

    candidates: Tuple[Node, ...]


@dataclass
class GetPeerCandidatesRequest(BaseRequestResponseEvent[GetPeerCandidatesResponse]):

    num_requested: int
    connected_remotes: Set[Node]

    @staticmethod
    def expected_response_type() -> Type[GetPeerCandidatesResponse]:
        return GetPeerCandidatesResponse
