from abc import (
    ABC,
    abstractmethod,
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


class HasRemoteEvent(BaseEvent, ABC):
    """
    Abstract base event for event types that carry a ``Node`` on the ``remote`` property.
    """

    @property
    @abstractmethod
    def remote(self) -> Node:
        pass


class ConnectToNodeCommand(HasRemoteEvent):
    """
    Event that wraps a node URI that the pool should connect to.
    """

    def __init__(self, remote: Node) -> None:
        self._remote = remote

    @property
    def remote(self) -> Node:
        return self._remote


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


class DisconnectPeerEvent(HasRemoteEvent):
    """
    Event broadcasted when we want to disconnect from a peer
    """

    def __init__(self, remote: Node, reason: DisconnectReason) -> None:
        self._remote = remote
        self.reason = reason

    @property
    def remote(self) -> Node:
        return self._remote


class PeerPoolMessageEvent(HasRemoteEvent):
    """
    Base event for all peer messages that are relayed on the event bus. The events are mapped
    to individual subclasses for every different ``cmd`` to allow efficient consumption through
    the event bus.
    """

    def __init__(self, remote: Node, cmd: Command, msg: PayloadType) -> None:
        self._remote = remote
        self.cmd = cmd
        self.msg = msg

    @property
    def remote(self) -> Node:
        return self._remote
