from abc import ABC
import logging
import operator
import struct
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    TYPE_CHECKING,
    Union,
)

from mypy_extensions import (
    TypedDict,
)

import snappy

import rlp
from rlp import sedes

from eth.constants import NULL_BYTE

from p2p.exceptions import (
    MalformedMessage,
    NoMatchingPeerCapabilities,
)
from p2p._utils import get_devp2p_cmd_id

# Workaround for import cycles caused by type annotations:
# http://mypy.readthedocs.io/en/latest/common_issues.html#import-cycles
if TYPE_CHECKING:
    from p2p.peer import BasePeer  # noqa: F401


class TypedDictPayload(TypedDict):
    pass


PayloadType = Union[
    Dict[str, Any],
    List[rlp.Serializable],
    Tuple[rlp.Serializable, ...],
    TypedDictPayload,
]

# A payload to be delivered with a request
TRequestPayload = TypeVar('TRequestPayload', bound=PayloadType, covariant=True)

# for backwards compatibility for internal references in p2p:
_DecodedMsgType = PayloadType


StructureType = Union[
    Tuple[Tuple[str, Any], ...],
]


class Command:
    _cmd_id: int = None
    decode_strict = True
    structure: StructureType

    _logger: logging.Logger = None

    def __init__(self, cmd_id_offset: int, snappy_support: bool) -> None:
        self.cmd_id_offset = cmd_id_offset
        self.cmd_id = cmd_id_offset + self._cmd_id
        self.snappy_support = snappy_support

    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = logging.getLogger(f"p2p.protocol.{type(self).__name__}")
        return self._logger

    @property
    def is_base_protocol(self) -> bool:
        return self.cmd_id_offset == 0

    def __str__(self) -> str:
        return f"{type(self).__name__} (cmd_id={self.cmd_id})"

    def encode_payload(self, data: Union[PayloadType, sedes.CountableList]) -> bytes:
        if isinstance(data, dict):
            if not isinstance(self.structure, tuple):
                raise ValueError(
                    "Command.structure must be a list when data is a dict.  Got "
                    f"{self.structure}"
                )
            expected_keys = sorted(name for name, _ in self.structure)
            data_keys = sorted(data.keys())
            if data_keys != expected_keys:
                raise ValueError(
                    f"Keys in data dict ({data_keys}) do not match expected keys ({expected_keys})"
                )
            data = tuple(data[name] for name, _ in self.structure)

        if isinstance(self.structure, sedes.CountableList):
            encoder = self.structure
        else:
            encoder = sedes.List([type_ for _, type_ in self.structure])
        return rlp.encode(data, sedes=encoder)

    def decode_payload(self, rlp_data: bytes) -> PayloadType:
        if isinstance(self.structure, sedes.CountableList):
            decoder = self.structure
        else:
            decoder = sedes.List(
                [type_ for _, type_ in self.structure], strict=self.decode_strict)
        try:
            data = rlp.decode(rlp_data, sedes=decoder, recursive_cache=True)
        except rlp.DecodingError as err:
            raise MalformedMessage(f"Malformed {type(self).__name__} message: {err!r}") from err

        if isinstance(self.structure, sedes.CountableList):
            return data
        return {
            field_name: value
            for ((field_name, _), value)
            in zip(self.structure, data)
        }

    def decode(self, data: bytes) -> PayloadType:
        packet_type = get_devp2p_cmd_id(data)
        if packet_type != self.cmd_id:
            raise MalformedMessage(f"Wrong packet type: {packet_type}, expected {self.cmd_id}")

        compressed_payload = data[1:]
        encoded_payload = self.decompress_payload(compressed_payload)

        return self.decode_payload(encoded_payload)

    def decompress_payload(self, raw_payload: bytes) -> bytes:
        # Do the Snappy Decompression only if Snappy Compression is supported by the protocol
        if self.snappy_support:
            return snappy.decompress(raw_payload)
        else:
            return raw_payload

    def compress_payload(self, raw_payload: bytes) -> bytes:
        # Do the Snappy Compression only if Snappy Compression is supported by the protocol
        if self.snappy_support:
            return snappy.compress(raw_payload)
        else:
            return raw_payload

    def encode(self, data: PayloadType) -> Tuple[bytes, bytes]:
        encoded_payload = self.encode_payload(data)
        compressed_payload = self.compress_payload(encoded_payload)

        enc_cmd_id = rlp.encode(self.cmd_id, sedes=rlp.sedes.big_endian_int)
        frame_size = len(enc_cmd_id) + len(compressed_payload)
        if frame_size.bit_length() > 24:
            raise ValueError("Frame size has to fit in a 3-byte integer")

        # Drop the first byte as, per the spec, frame_size must be a 3-byte int.
        header = struct.pack('>I', frame_size)[1:]
        # All clients seem to ignore frame header data, so we do the same, although I'm not sure
        # why geth uses the following value:
        # https://github.com/ethereum/go-ethereum/blob/master/p2p/rlpx.go#L556
        zero_header = b'\xc2\x80\x80'
        header += zero_header
        header = _pad_to_16_byte_boundary(header)

        body = _pad_to_16_byte_boundary(enc_cmd_id + compressed_payload)
        return header, body


class BaseRequest(ABC, Generic[TRequestPayload]):
    """
    Must define command_payload during init. This is the data that will
    be sent to the peer with the request command.
    """
    # Defined at init time, with specific parameters:
    command_payload: TRequestPayload

    # Defined as class attributes in subclasses
    # outbound command type
    cmd_type: Type[Command]
    # response command type
    response_type: Type[Command]


CapabilityType = Tuple[str, int]


class Protocol:
    peer: 'BasePeer'
    name: str = None
    version: int = None
    cmd_length: int = None
    # Command classes that this protocol supports.
    _commands: Tuple[Type[Command], ...]

    _logger: logging.Logger = None

    def __init__(self, peer: 'BasePeer', cmd_id_offset: int, snappy_support: bool) -> None:
        self.peer = peer
        self.cmd_id_offset = cmd_id_offset
        self.snappy_support = snappy_support
        self.commands = [cmd_class(cmd_id_offset, snappy_support) for cmd_class in self._commands]
        self.cmd_by_type = {type(cmd): cmd for cmd in self.commands}
        self.cmd_by_id = {cmd.cmd_id: cmd for cmd in self.commands}

    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            self._logger = logging.getLogger(f"p2p.protocol.{type(self).__name__}")
        return self._logger

    def send(self, header: bytes, body: bytes) -> None:
        self.peer.send(header, body)

    def send_request(self, request: BaseRequest[PayloadType]) -> None:
        command = self.cmd_by_type[request.cmd_type]
        header, body = command.encode(request.command_payload)
        self.send(header, body)

    def supports_command(self, cmd_type: Type[Command]) -> bool:
        return cmd_type in self.cmd_by_type

    @classmethod
    def as_capability(cls) -> CapabilityType:
        return (cls.name, cls.version)

    def __repr__(self) -> str:
        return "(%s, %d)" % (self.name, self.version)


CapabilitiesType = Tuple[CapabilityType, ...]


def select_sub_protocol(protocols: Sequence[Type[Protocol]],
                        capabilities: CapabilitiesType) -> Type[Protocol]:
    """
    Return the highest version protocol from the provided `protocols` based on
    the provided remote `capabilities`.

    Return the protocol with the highest version that is present in the
    remote and stores an instance of it (with the appropriate cmd_id offset) in
    self.sub_proto.

    Raise NoMatchingPeerCapabilities if none of our supported protocols match one of the
    remote's protocols.

    Raise NotImplementedError if all protocols do not share the same name.
    """
    proto_names = set(proto.name for proto in protocols)
    if len(proto_names) != 1:
        raise NotImplementedError(
            "Negotiation of capabilities across multiple protocol names not "
            "implemented"
        )

    supported_capabilities = set(proto.as_capability() for proto in protocols)
    matching_capabilities = tuple(sorted(
        supported_capabilities.intersection(capabilities),
        key=operator.itemgetter(1),
        reverse=True,
    ))

    if not matching_capabilities:
        raise NoMatchingPeerCapabilities(
            f"No matching capabilities:\n"
            f" - {tuple(sorted(supported_capabilities))}\n"
            f" - {tuple(sorted(capabilities))}"
        )

    for match in matching_capabilities:
        for proto in protocols:
            if proto.as_capability() == match:
                return proto

    raise NoMatchingPeerCapabilities()


def _pad_to_16_byte_boundary(data: bytes) -> bytes:
    """Pad the given data with NULL_BYTE up to the next 16-byte boundary."""
    remainder = len(data) % 16
    if remainder != 0:
        data += NULL_BYTE * (16 - remainder)
    return data
