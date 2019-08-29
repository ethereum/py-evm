from abc import ABC, abstractmethod
import asyncio
from typing import (
    Any,
    AsyncContextManager,
    AsyncIterator,
    Awaitable,
    Callable,
    ClassVar,
    ContextManager,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TYPE_CHECKING,
    TypeVar,
    Union,
)


from rlp import sedes

from cancel_token import CancelToken

from eth_utils import ExtendedDebugLogger

from eth_keys import datatypes

from p2p.typing import Capability, Capabilities, Payload, Structure
from p2p.transport_state import TransportState

if TYPE_CHECKING:
    from p2p.handshake import DevP2PReceipt  # noqa: F401
    from p2p.p2p_proto import (  # noqa: F401
        BaseP2PProtocol,
    )


TAddress = TypeVar('TAddress', bound='AddressAPI')


class AddressAPI(ABC):
    udp_port: int
    tcp_port: int

    @abstractmethod
    def __init__(self, ip: str, udp_port: int, tcp_port: int = 0) -> None:
        ...

    @property
    @abstractmethod
    def is_loopback(self) -> bool:
        ...

    @property
    @abstractmethod
    def is_unspecified(self) -> bool:
        ...

    @property
    @abstractmethod
    def is_reserved(self) -> bool:
        ...

    @property
    @abstractmethod
    def is_private(self) -> bool:
        ...

    @property
    @abstractmethod
    def ip(self) -> str:
        ...

    @abstractmethod
    def __eq__(self, other: Any) -> bool:
        ...

    @abstractmethod
    def to_endpoint(self) -> List[bytes]:
        ...

    @classmethod
    @abstractmethod
    def from_endpoint(cls: Type[TAddress],
                      ip: str,
                      udp_port: bytes,
                      tcp_port: bytes = b'\x00\x00') -> TAddress:
        ...


TNode = TypeVar('TNode', bound='NodeAPI')


class NodeAPI(ABC):
    pubkey: datatypes.PublicKey
    address: AddressAPI
    id: int

    @abstractmethod
    def __init__(self, pubkey: datatypes.PublicKey, address: AddressAPI) -> None:
        ...

    @classmethod
    @abstractmethod
    def from_uri(cls: Type[TNode], uri: str) -> TNode:
        ...

    @abstractmethod
    def uri(self) -> str:
        ...

    @abstractmethod
    def distance_to(self, id: int) -> int:
        ...

    # mypy doesn't have support for @total_ordering
    # https://github.com/python/mypy/issues/4610
    @abstractmethod
    def __lt__(self, other: Any) -> bool:
        ...

    @abstractmethod
    def __eq__(self, other: Any) -> bool:
        ...

    @abstractmethod
    def __ne__(self, other: Any) -> bool:
        ...

    @abstractmethod
    def __hash__(self) -> int:
        ...


class CommandAPI(ABC):
    structure: Structure

    cmd_id: int
    cmd_id_offset: int
    snappy_support: bool

    @abstractmethod
    def __init__(self, cmd_id_offset: int, snappy_support: bool) -> None:
        ...

    @property
    @abstractmethod
    def is_base_protocol(self) -> bool:
        ...

    @abstractmethod
    def encode_payload(self, data: Union[Payload, sedes.CountableList]) -> bytes:
        ...

    @abstractmethod
    def decode_payload(self, rlp_data: bytes) -> Payload:
        ...

    @abstractmethod
    def encode(self, data: Payload) -> Tuple[bytes, bytes]:
        ...

    @abstractmethod
    def decode(self, data: bytes) -> Payload:
        ...

    @abstractmethod
    def decompress_payload(self, raw_payload: bytes) -> bytes:
        ...

    @abstractmethod
    def compress_payload(self, raw_payload: bytes) -> bytes:
        ...


# A payload to be delivered with a request
TRequestPayload = TypeVar('TRequestPayload', bound=Payload, covariant=True)


class RequestAPI(ABC, Generic[TRequestPayload]):
    """
    Must define command_payload during init. This is the data that will
    be sent to the peer with the request command.
    """
    # Defined at init time, with specific parameters:
    command_payload: TRequestPayload

    # Defined as class attributes in subclasses
    # outbound command type
    cmd_type: Type[CommandAPI]
    # response command type
    response_type: Type[CommandAPI]


class TransportAPI(ABC):
    remote: NodeAPI
    read_state: TransportState

    @property
    @abstractmethod
    def is_closing(self) -> bool:
        ...

    @property
    @abstractmethod
    def public_key(self) -> datatypes.PublicKey:
        ...

    @abstractmethod
    async def read(self, n: int, token: CancelToken) -> bytes:
        ...

    @abstractmethod
    def write(self, data: bytes) -> None:
        ...

    @abstractmethod
    async def recv(self, token: CancelToken) -> bytes:
        ...

    @abstractmethod
    def send(self, header: bytes, body: bytes) -> None:
        ...

    @abstractmethod
    def close(self) -> None:
        ...


class ProtocolAPI(ABC):
    transport: TransportAPI
    name: ClassVar[str]
    version: ClassVar[int]

    cmd_length: int

    cmd_id_offset: int

    commands: Tuple[CommandAPI, ...]
    cmd_by_type: Dict[Type[CommandAPI], CommandAPI]
    cmd_by_id: Dict[int, CommandAPI]

    @abstractmethod
    def __init__(self, transport: TransportAPI, cmd_id_offset: int, snappy_support: bool) -> None:
        ...

    @abstractmethod
    def send_request(self, request: RequestAPI[Payload]) -> None:
        ...

    @classmethod
    @abstractmethod
    def supports_command(cls, cmd_type: Type[CommandAPI]) -> bool:
        ...

    @classmethod
    @abstractmethod
    def as_capability(cls) -> Capability:
        ...


TProtocol = TypeVar('TProtocol', bound=ProtocolAPI)


class MultiplexerAPI(ABC):
    cancel_token: CancelToken

    #
    # Transport API
    #
    @abstractmethod
    def get_transport(self) -> TransportAPI:
        ...

    #
    # Message Counts
    #
    @abstractmethod
    def get_total_msg_count(self) -> int:
        ...

    #
    # Proxy Transport methods
    #
    @property
    @abstractmethod
    def remote(self) -> NodeAPI:
        ...

    @property
    @abstractmethod
    def is_closing(self) -> bool:
        ...

    @abstractmethod
    def close(self) -> None:
        ...

    #
    # Protocol API
    #
    @abstractmethod
    def has_protocol(self, protocol_identifier: Union[ProtocolAPI, Type[ProtocolAPI]]) -> bool:
        ...

    @abstractmethod
    def get_protocol_by_type(self, protocol_class: Type[TProtocol]) -> TProtocol:
        ...

    @abstractmethod
    def get_base_protocol(self) -> 'BaseP2PProtocol':
        ...

    @abstractmethod
    def get_protocols(self) -> Tuple[ProtocolAPI, ...]:
        ...

    #
    # Streaming API
    #
    @abstractmethod
    def stream_protocol_messages(self,
                                 protocol_identifier: Union[ProtocolAPI, Type[ProtocolAPI]],
                                 ) -> AsyncIterator[Tuple[CommandAPI, Payload]]:
        ...

    #
    # Message reading and streaming API
    #
    def multiplex(self) -> AsyncContextManager[None]:
        ...


class ServiceEventsAPI(ABC):
    started: asyncio.Event
    stopped: asyncio.Event
    cleaned_up: asyncio.Event
    cancelled: asyncio.Event
    finished: asyncio.Event


TReturn = TypeVar('TReturn')


class AsyncioServiceAPI(ABC):
    events: ServiceEventsAPI
    cancel_token: CancelToken

    @property
    @abstractmethod
    def logger(self) -> ExtendedDebugLogger:
        ...

    @abstractmethod
    def cancel_nowait(self) -> None:
        ...

    @property
    @abstractmethod
    def is_cancelled(self) -> bool:
        ...

    @property
    @abstractmethod
    def is_running(self) -> bool:
        ...

    @abstractmethod
    async def run(
            self,
            finished_callback: Optional[Callable[['AsyncioServiceAPI'], None]] = None) -> None:
        ...

    @abstractmethod
    async def cancel(self) -> None:
        ...

    @abstractmethod
    def run_daemon(self, service: 'AsyncioServiceAPI') -> None:
        ...

    @abstractmethod
    async def wait(self,
                   awaitable: Awaitable[TReturn],
                   token: CancelToken = None,
                   timeout: float = None) -> TReturn:
        ...


class HandshakeReceiptAPI(ABC):
    protocol: ProtocolAPI


class HandlerSubscriptionAPI(ContextManager['HandlerSubscriptionAPI']):
    @abstractmethod
    def cancel(self) -> None:
        ...


ProtocolHandlerFn = Callable[['ConnectionAPI', CommandAPI, Payload], Awaitable[Any]]
CommandHandlerFn = Callable[['ConnectionAPI', Payload], Awaitable[Any]]


class ConnectionAPI(AsyncioServiceAPI):
    protocol_receipts: Tuple[HandshakeReceiptAPI, ...]

    #
    # Primary properties of the connection
    #
    is_dial_out: bool

    @property
    @abstractmethod
    def is_dial_in(self) -> bool:
        ...

    @property
    @abstractmethod
    def remote(self) -> NodeAPI:
        ...

    #
    # Subscriptions/Handler API
    #
    @abstractmethod
    def start_protocol_streams(self) -> None:
        ...

    @abstractmethod
    def add_protocol_handler(self,
                             protocol_type: Type[ProtocolAPI],
                             handler_fn: ProtocolHandlerFn,
                             ) -> HandlerSubscriptionAPI:
        ...

    @abstractmethod
    def add_command_handler(self,
                            command_type: Type[CommandAPI],
                            handler_fn: CommandHandlerFn,
                            ) -> HandlerSubscriptionAPI:
        ...

    #
    # Access to underlying Multiplexer
    #
    @abstractmethod
    def get_multiplexer(self) -> MultiplexerAPI:
        ...

    #
    # Base Protocol shortcuts
    #
    @abstractmethod
    def get_base_protocol(self) -> 'BaseP2PProtocol':
        ...

    @abstractmethod
    def get_p2p_receipt(self) -> 'DevP2PReceipt':
        ...

    #
    # Connection Metadata
    #
    @property
    @abstractmethod
    def remote_capabilities(self) -> Capabilities:
        ...

    @property
    @abstractmethod
    def remote_p2p_version(self) -> int:
        ...

    @property
    @abstractmethod
    def client_version_string(self) -> str:
        ...

    @property
    @abstractmethod
    def safe_client_version_string(self) -> str:
        ...
