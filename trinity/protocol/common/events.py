from typing import (
    Type,
)

from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
)

from p2p.peer import (
    IdentifiablePeer,
)
from p2p.p2p_proto import (
    DisconnectReason,
)


class ConnectToNodeCommand(BaseEvent):
    """
    Event that wraps a node URI that the pool should connect to.
    """

    def __init__(self, node: str) -> None:
        self.node = node


class PeerCountResponse(BaseEvent):
    """
    Response event that wraps the count of peers connected to the pool.
    """

    def __init__(self, peer_count: int) -> None:
        self.peer_count = peer_count


class PeerCountRequest(BaseRequestResponseEvent[PeerCountResponse]):
    """
    Request event to get the count of peers connected to the pool.
    """

    @staticmethod
    def expected_response_type() -> Type[PeerCountResponse]:
        return PeerCountResponse


class DisconnectPeerEvent(BaseEvent):
    """
    Event broadcasted when we want to disconnect from a peer
    """

    def __init__(self, peer: IdentifiablePeer, reason: DisconnectReason) -> None:
        self.peer = peer
        self.reason = reason
