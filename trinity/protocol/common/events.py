from dataclasses import (
    dataclass,
)
from typing import (
    Type,
)

from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
)

from p2p.kademlia import Node
from p2p.p2p_proto import (
    DisconnectReason,
)
from p2p.protocol import (
    Command,
    PayloadType,
)


@dataclass
class HasRemoteEvent(BaseEvent):
    """
    Abstract base event for event types that carry a ``Node`` on the ``remote`` property.
    """

    remote: Node


@dataclass
class ConnectToNodeCommand(HasRemoteEvent):
    """
    Event that wraps a node URI that the pool should connect to.
    """
    pass


@dataclass
class PeerCountResponse(BaseEvent):
    """
    Response event that wraps the count of peers connected to the pool.
    """

    peer_count: int


class PeerCountRequest(BaseRequestResponseEvent[PeerCountResponse]):
    """
    Request event to get the count of peers connected to the pool.
    """

    @staticmethod
    def expected_response_type() -> Type[PeerCountResponse]:
        return PeerCountResponse


@dataclass
class DisconnectPeerEvent(HasRemoteEvent):
    """
    Event broadcasted when we want to disconnect from a peer
    """

    reason: DisconnectReason


@dataclass
class PeerJoinedEvent(HasRemoteEvent):
    """
    Event broadcasted when a new peer joined the pool.
    """
    pass


@dataclass
class PeerLeftEvent(HasRemoteEvent):
    """
    Event broadcasted when a peer left the pool.
    """
    pass


@dataclass
class PeerPoolMessageEvent(HasRemoteEvent):
    """
    Base event for all peer messages that are relayed on the event bus. The events are mapped
    to individual subclasses for every different ``cmd`` to allow efficient consumption through
    the event bus.
    """

    cmd: Command
    msg: PayloadType
