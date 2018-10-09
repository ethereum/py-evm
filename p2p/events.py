from typing import (
    Type,
    TYPE_CHECKING,
)

from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
)

if TYPE_CHECKING:
    from p2p.peer import BasePeer


class PeerConnectedEvent(BaseEvent):
    """
    Broadcasted when a new peer of any kind connects to the peer pool.
    """
    def __init__(self, peer: 'BasePeer'):
        self.peer = peer


class PeerCountResponse(BaseEvent):

    def __init__(self, peer_count: int) -> None:
        self.peer_count = peer_count


class PeerCountRequest(BaseRequestResponseEvent[PeerCountResponse]):

    @staticmethod
    def expected_response_type() -> Type[PeerCountResponse]:
        return PeerCountResponse
