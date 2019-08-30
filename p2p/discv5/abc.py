from abc import (
    ABC,
    abstractmethod,
)
from typing import (
    AsyncContextManager,
    AsyncIterable,
    Generic,
    Type,
    TypeVar,
)

from p2p.discv5.enr import (
    ENR,
)
from p2p.discv5.channel_services import (
    IncomingMessage,
)
from p2p.discv5.identity_schemes import (
    IdentityScheme,
    IdentitySchemeRegistry,
)
from p2p.discv5.messages import (
    BaseMessage,
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
    @abstractmethod
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
    @abstractmethod
    def tag(self) -> Tag:
        """The tag used for message packets sent by this node to the peer."""
        ...


class EnrDbApi(ABC):
    @abstractmethod
    def __init__(self, identity_scheme_registry: IdentitySchemeRegistry):
        ...

    @property
    @abstractmethod
    def identity_scheme_registry(self) -> IdentitySchemeRegistry:
        ...

    @abstractmethod
    async def insert(self, enr: ENR) -> None:
        """Insert an ENR into the database."""
        ...

    @abstractmethod
    async def update(self, enr: ENR) -> None:
        """Update an existing ENR if the sequence number is greater."""
        ...

    @abstractmethod
    async def remove(self, node_id: NodeID) -> None:
        """Remove an ENR from the db."""
        ...

    @abstractmethod
    async def insert_or_update(self, enr: ENR) -> None:
        """Insert or update an ENR depending if it is already present already or not."""
        ...

    @abstractmethod
    async def get(self, node_id: NodeID) -> ENR:
        """Get an ENR by its node id."""
        ...

    @abstractmethod
    async def contains(self, node_id: NodeID) -> bool:
        """Check if the db contains an ENR with the given node id."""
        ...


ChannelContentType = TypeVar("ChannelContentType")
ChannelHandlerAsyncContextManager = AsyncContextManager[
    "ChannelHandlerSubscriptionAPI[ChannelContentType]"
]


class ChannelHandlerSubscriptionAPI(Generic[ChannelContentType],
                                    AsyncIterable[ChannelContentType],
                                    AsyncContextManager[
                                        "ChannelHandlerSubscriptionAPI[ChannelContentType]"],
                                    ):
    @abstractmethod
    def cancel(self) -> None:
        ...

    @abstractmethod
    async def receive(self) -> ChannelContentType:
        ...


class MessageDispatcherAPI(ABC):
    @abstractmethod
    def get_free_request_id(self, node_id: NodeID) -> int:
        """Get a currently unused request id for requests to the given node."""
        ...

    @abstractmethod
    async def request(self, receiver_node_id: NodeID, message: BaseMessage) -> IncomingMessage:
        """Send a request to the given peer and return the response.

        This is the primary interface for requesting data from a peer. Internally, it will look up
        the peer's ENR in the database, extract endpoint information from it, add a response
        handler, send the request, wait for the response, and finally remove the handler again.

        This method cannot be used if the response consists of multiple messages.
        """
        ...

    @abstractmethod
    def add_request_handler(self,
                            message_type: int,
                            ) -> ChannelHandlerSubscriptionAPI[IncomingMessage]:
        """Add a request handler for messages of a given type.

        Only one handler per message type can be added.
        """
        ...

    @abstractmethod
    def add_response_handler(self,
                             remote_node_id: NodeID,
                             request_id: int,
                             ) -> ChannelHandlerSubscriptionAPI[IncomingMessage]:
        """Add a response handler.

        All messages sent by the given peer with the given request id will be send to the returned
        handler's channel.
        """
        ...
