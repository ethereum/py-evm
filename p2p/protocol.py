from abc import ABC
import logging
import struct
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Tuple,
    Type,
    TypeVar,
    TYPE_CHECKING,
    Union,
)

import rlp
from rlp import sedes

from eth.constants import NULL_BYTE

from p2p.exceptions import (
    MalformedMessage,
)
from p2p.utils import get_devp2p_cmd_id

# Workaround for import cycles caused by type annotations:
# http://mypy.readthedocs.io/en/latest/common_issues.html#import-cycles
if TYPE_CHECKING:
    from p2p.peer import BasePeer  # noqa: F401

PayloadType = Union[
    Dict[str, Any],
    List[rlp.Serializable],
    Tuple[rlp.Serializable, ...],
]

# A payload to be delivered with a request
TRequestPayload = TypeVar('TRequestPayload', bound=PayloadType, covariant=True)

# for backwards compatibility for internal references in p2p:
_DecodedMsgType = PayloadType


class Command:
    _cmd_id: int = None
    decode_strict = True
    structure: List[Tuple[str, Any]] = []

    _logger: logging.Logger = None

    def __init__(self, cmd_id_offset: int) -> None:
        self.cmd_id_offset = cmd_id_offset
        self.cmd_id = cmd_id_offset + self._cmd_id

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
        if isinstance(data, dict):  # convert dict to ordered list
            if not isinstance(self.structure, list):
                raise ValueError("Command.structure must be a list when data is a dict")
            expected_keys = sorted(name for name, _ in self.structure)
            data_keys = sorted(data.keys())
            if data_keys != expected_keys:
                raise ValueError(
                    f"Keys in data dict ({data_keys}) do not match expected keys ({expected_keys})"
                )
            data = [data[name] for name, _ in self.structure]
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
        return self.decode_payload(data[1:])

    def encode(self, data: PayloadType) -> Tuple[bytes, bytes]:
        payload = self.encode_payload(data)
        enc_cmd_id = rlp.encode(self.cmd_id, sedes=rlp.sedes.big_endian_int)
        frame_size = len(enc_cmd_id) + len(payload)
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

        body = _pad_to_16_byte_boundary(enc_cmd_id + payload)
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


class Protocol:
    peer: 'BasePeer'
    logger = logging.getLogger("p2p.protocol.Protocol")
    name: str = None
    version: int = None
    cmd_length: int = None
    # List of Command classes that this protocol supports.
    _commands: List[Type[Command]] = []

    def __init__(self, peer: 'BasePeer', cmd_id_offset: int) -> None:
        self.peer = peer
        self.cmd_id_offset = cmd_id_offset
        self.commands = [cmd_class(cmd_id_offset) for cmd_class in self._commands]
        self.cmd_by_type = {cmd_class: cmd_class(cmd_id_offset) for cmd_class in self._commands}
        self.cmd_by_id = dict((cmd.cmd_id, cmd) for cmd in self.commands)

    def send(self, header: bytes, body: bytes) -> None:
        self.peer.send(header, body)

    def send_request(self, request: BaseRequest[PayloadType]) -> None:
        command = self.cmd_by_type[request.cmd_type]
        header, body = command.encode(request.command_payload)
        self.send(header, body)

    def supports_command(self, cmd_type: Type[Command]) -> bool:
        return cmd_type in self.cmd_by_type

    def __repr__(self) -> str:
        return "(%s, %d)" % (self.name, self.version)


def _pad_to_16_byte_boundary(data: bytes) -> bytes:
    """Pad the given data with NULL_BYTE up to the next 16-byte boundary."""
    remainder = len(data) % 16
    if remainder != 0:
        data += NULL_BYTE * (16 - remainder)
    return data
