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


class TrackPeerEvent(BasePeerDBEvent):
    def __init__(self,
                 remote: Node,
                 is_outbound: bool,
                 last_connected_at: Optional[datetime.datetime],
                 genesis_hash: Hash32,
                 protocol: str,
                 protocol_version: int,
                 network_id: int) -> None:
        self.remote = remote
        self.is_outbound = is_outbound
        self.last_connected_at = last_connected_at
        self.genesis_hash = genesis_hash
        self.protocol = protocol
        self.protocol_version = protocol_version
        self.network_id = network_id


class GetPeerCandidatesResponse(BasePeerDBEvent):
    def __init__(self, candidates: Tuple[Node, ...]) -> None:
        self.candidates = candidates


class GetPeerCandidatesRequest(BaseRequestResponseEvent[GetPeerCandidatesResponse]):
    def __init__(self, num_requested: int, connected_remotes: Set[Node]) -> None:
        self.num_requested = num_requested
        self.connected_remotes = connected_remotes

    @staticmethod
    def expected_response_type() -> Type[GetPeerCandidatesResponse]:
        return GetPeerCandidatesResponse
