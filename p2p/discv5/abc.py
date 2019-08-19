from abc import (
    ABC,
    abstractmethod,
)
from typing import (
    Type,
)

from p2p.discv5.enr import (
    ENR,
)
from p2p.discv5.identity_schemes import (
    IdentityScheme,
)
from p2p.discv5.packets import (
    Packet,
)
from p2p.discv5.typing import (
    NodeID,
    HandshakeResult,
    Tag,
)


class HandshakeParticipantAPI(ABC):
    def __init__(self,
                 is_initiator: bool,
                 local_private_key: bytes,
                 local_enr: ENR,
                 remote_node_id: NodeID,
                 ) -> None:
        ...

    @property
    @abstractmethod
    def first_packet_to_send(self) -> Packet:
        """The first packet we have to send the peer."""
        ...

    @abstractmethod
    def is_response_packet(self, packet: Packet) -> bool:
        """Check if the given packet is the response we need to complete the handshake."""
        ...

    @abstractmethod
    def complete_handshake(self, response_packet: Packet) -> HandshakeResult:
        """Complete the handshake using a response packet received from the peer."""
        ...

    @property
    @abstractmethod
    def is_initiator(self) -> bool:
        """`True` if the handshake was initiated by us, `False` if it was initiated by the peer."""
        ...

    @property
    @abstractmethod
    def identity_scheme(self) -> Type[IdentityScheme]:
        """The identity scheme used during the handshake."""
        ...

    @property
    @abstractmethod
    def local_private_key(self) -> bytes:
        """The static node key of this node."""
        ...

    @property
    @abstractmethod
    def local_enr(self) -> ENR:
        """The ENR of this node"""
        ...

    @property
    @abstractmethod
    def local_node_id(self) -> NodeID:
        """The node id of this node."""
        ...

    @property
    @abstractmethod
    def remote_node_id(self) -> NodeID:
        """The peer's node id."""
        ...

    @property
    def tag(self) -> Tag:
        """The tag used for message packets sent by this node to the peer."""
        ...
