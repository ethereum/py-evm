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
    Generic,
    Hashable,
    List,
    Optional,
    Tuple,
    Type,
    TYPE_CHECKING,
    TypeVar,
    Union,
)
import uuid

from cancel_token import CancelToken

from eth_utils import ExtendedDebugLogger

from eth_keys import keys

from p2p.typing import (
    Capabilities,
    Capability,
    TCommandPayload,
)
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
    pubkey: keys.PublicKey
    address: AddressAPI
    id: int

    @abstractmethod
    def __init__(self, pubkey: keys.PublicKey, address: AddressAPI) -> None:
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


class SessionAPI(ABC, Hashable):
    id: uuid.UUID
    remote: NodeAPI


class SerializationCodecAPI(ABC, Generic[TCommandPayload]):
    @abstractmethod
    def encode(self, payload: TCommandPayload) -> bytes:
        ...

    @abstractmethod
    def decode(self, data: bytes) -> TCommandPayload:
        ...


class CompressionCodecAPI(ABC):
    @abstractmethod
    def compress(self, data: bytes) -> bytes:
        ...

    @abstractmethod
    def decompress(self, data: bytes) -> bytes:
        ...


class MessageAPI(ABC):
    header: bytes
    body: bytes
    # This is the combined `command_id_offset + protocol_command_id`
    command_id: int
    # This is the `body` with the first byte stripped off
    encoded_payload: bytes


class CommandAPI(ABC, Generic[TCommandPayload]):
    # This is the local `id` for the command within the context of the
    # protocol.
    protocol_command_id: ClassVar[int]
    serialization_codec: SerializationCodecAPI[TCommandPayload]
    compression_codec: CompressionCodecAPI

    payload: TCommandPayload

    @abstractmethod
    def __init__(self, payload: TCommandPayload) -> None:
        ...

    @abstractmethod
    def encode(self, negotiated_command_id: int, snappy_support: bool) -> MessageAPI:
        ...

    @classmethod
    @abstractmethod
    def decode(cls: Type['TCommand'], message: MessageAPI, snappy_support: bool) -> 'TCommand':
        ...


TCommand = TypeVar("TCommand", bound=CommandAPI[Any])


class TransportAPI(ABC):
    session: SessionAPI
    remote: NodeAPI
    read_state: TransportState
    logger: ExtendedDebugLogger

    @property
    @abstractmethod
    def is_closing(self) -> bool:
        ...

    @property
    @abstractmethod
    def public_key(self) -> keys.PublicKey:
        ...

    @abstractmethod
    async def read(self, n: int, token: CancelToken) -> bytes:
        ...

    @abstractmethod
    def write(self, data: bytes) -> None:
        ...

    @abstractmethod
    async def recv(self, token: CancelToken) -> MessageAPI:
        ...

    @abstractmethod
    def send(self, message: MessageAPI) -> None:
        ...

    @abstractmethod
    def close(self) -> None:
        ...


class ProtocolAPI(ABC):
    name: ClassVar[str]
    version: ClassVar[int]

    # Command classes that this protocol supports.
    commands: ClassVar[Tuple[Type[CommandAPI[Any]], ...]]
    command_length: ClassVar[int]

    command_id_offset: int
    snappy_support: bool
    transport: TransportAPI

    @abstractmethod
    def __init__(self,
                 transport: TransportAPI,
                 negotiated_command_id_offset: int,
                 snappy_support: bool) -> None:
        ...

    @classmethod
    @abstractmethod
    def supports_command(cls, command_type: Type[CommandAPI[Any]]) -> bool:
        ...

    @classmethod
    @abstractmethod
    def as_capability(cls) -> Capability:
        ...

    @abstractmethod
    def get_command_type_for_command_id(self, command_id: int) -> Type[CommandAPI[Any]]:
        ...

    @abstractmethod
    def send(self, command: CommandAPI[Any]) -> None:
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
    # Proxy Transport properties and methods
    #
    @property
    @abstractmethod
    def session(self) -> SessionAPI:
        ...

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

    @abstractmethod
    def get_protocol_for_command_type(self, command_type: Type[CommandAPI[Any]]) -> ProtocolAPI:
        ...

    #
    # Streaming API
    #
    @abstractmethod
    def stream_protocol_messages(self,
                                 protocol_identifier: Union[ProtocolAPI, Type[ProtocolAPI]],
                                 ) -> AsyncIterator[CommandAPI[Any]]:
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

    @property
    @abstractmethod
    def is_operational(self) -> bool:
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
    def call_later(self, delay: float, callback: 'Callable[..., None]', *args: Any) -> None:
        ...

    @abstractmethod
    async def wait(self,
                   awaitable: Awaitable[TReturn],
                   token: CancelToken = None,
                   timeout: float = None) -> TReturn:
        ...


class HandshakeReceiptAPI(ABC):
    protocol: ProtocolAPI


THandshakeReceipt = TypeVar('THandshakeReceipt', bound=HandshakeReceiptAPI)


class HandshakerAPI(ABC):
    logger: ExtendedDebugLogger

    protocol_class: Type[ProtocolAPI]

    @abstractmethod
    async def do_handshake(self,
                           multiplexer: MultiplexerAPI,
                           protocol: ProtocolAPI) -> HandshakeReceiptAPI:
        """
        Perform the actual handshake for the protocol.
        """
        ...


QualifierFn = Callable[['ConnectionAPI', 'LogicAPI'], bool]


class LogicAPI(ABC):
    @abstractmethod
    def as_behavior(self, qualifier: QualifierFn = None) -> 'BehaviorAPI':
        ...

    @abstractmethod
    def apply(self, connection: 'ConnectionAPI') -> AsyncContextManager[None]:
        ...


TLogic = TypeVar('TLogic', bound=LogicAPI)


class BehaviorAPI(ABC):
    qualifier: QualifierFn
    logic: Any

    @abstractmethod
    def should_apply_to(self, connection: 'ConnectionAPI') -> bool:
        ...

    @abstractmethod
    def apply(self, connection: 'ConnectionAPI') -> AsyncContextManager[None]:
        """
        Context manager API used programatically by the `ContextManager` to
        apply the behavior to the connection during the lifecycle of the
        connection.
        """
        ...


TBehavior = TypeVar('TBehavior', bound=BehaviorAPI)


class SubscriptionAPI(ContextManager['SubscriptionAPI']):
    @abstractmethod
    def cancel(self) -> None:
        ...


HandlerFn = Callable[['ConnectionAPI', CommandAPI[Any]], Awaitable[Any]]


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
    def session(self) -> SessionAPI:
        ...

    @property
    @abstractmethod
    def remote(self) -> NodeAPI:
        ...

    @property
    @abstractmethod
    def is_closing(self) -> bool:
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
                             handler_fn: HandlerFn,
                             ) -> SubscriptionAPI:
        ...

    @abstractmethod
    def add_command_handler(self,
                            command_type: Type[CommandAPI[Any]],
                            handler_fn: HandlerFn,
                            ) -> SubscriptionAPI:
        ...

    #
    # Behavior API
    #
    @abstractmethod
    def add_logic(self, name: str, logic: LogicAPI) -> SubscriptionAPI:
        ...

    @abstractmethod
    def remove_logic(self, name: str) -> None:
        ...

    @abstractmethod
    def has_logic(self, name: str) -> bool:
        ...

    @abstractmethod
    def get_logic(self, name: str, logic_type: Type[TLogic]) -> TLogic:
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
    # Protocol APIS
    #
    @abstractmethod
    def has_protocol(self, protocol_identifier: Union[ProtocolAPI, Type[ProtocolAPI]]) -> bool:
        ...

    @abstractmethod
    def get_protocols(self) -> Tuple[ProtocolAPI, ...]:
        ...

    @abstractmethod
    def get_protocol_by_type(self, protocol_type: Type[TProtocol]) -> TProtocol:
        ...

    @abstractmethod
    def get_protocol_for_command_type(self, command_type: Type[CommandAPI[Any]]) -> ProtocolAPI:
        ...

    @abstractmethod
    def get_receipt_by_type(self, receipt_type: Type[THandshakeReceipt]) -> THandshakeReceipt:
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
