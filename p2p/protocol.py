import logging
import struct
from typing import (  # noqa: F401
    Any,
    Dict,
    List,
    Tuple,
    Type,
    TYPE_CHECKING,
    Union,
)

import rlp
from rlp import sedes

from evm.constants import NULL_BYTE

from p2p.utils import get_devp2p_cmd_id


# Workaround for import cycles caused by type annotations:
# http://mypy.readthedocs.io/en/latest/common_issues.html#import-cycles
if TYPE_CHECKING:
    from p2p.peer import ChainInfo, BasePeer  # noqa: F401


_DecodedMsgType = Union[
    Dict[str, Any],
    List[rlp.Serializable],
]


class Command:
    _cmd_id = None  # type: int
    decode_strict = True
    structure = []  # type: List[Tuple[str, Any]]

    def __init__(self, proto: 'Protocol') -> None:
        self.proto = proto

    def __str__(self):
        return "{} (cmd_id={})".format(self.__class__.__name__, self.cmd_id)

    @property
    def cmd_id(self) -> int:
        return self.proto.cmd_id_offset + self._cmd_id

    def encode_payload(self, data: Union[_DecodedMsgType, sedes.CountableList]) -> bytes:
        if isinstance(data, dict):  # convert dict to ordered list
            if not isinstance(self.structure, list):
                raise ValueError("Command.structure must be a list when data is a dict")
            expected_keys = sorted(name for name, _ in self.structure)
            data_keys = sorted(data.keys())
            if data_keys != expected_keys:
                raise ValueError("Keys in data dict ({}) do not match expected keys ({})".format(
                    data_keys, expected_keys))
            data = [data[name] for name, _ in self.structure]
        if isinstance(self.structure, sedes.CountableList):
            encoder = self.structure
        else:
            encoder = sedes.List([type_ for _, type_ in self.structure])
        return rlp.encode(data, sedes=encoder)

    def decode_payload(self, rlp_data: bytes) -> _DecodedMsgType:
        if isinstance(self.structure, sedes.CountableList):
            decoder = self.structure
        else:
            decoder = sedes.List(
                [type_ for _, type_ in self.structure], strict=self.decode_strict)
        data = rlp.decode(rlp_data, sedes=decoder)
        if isinstance(self.structure, sedes.CountableList):
            return data
        return {
            field_name: value
            for ((field_name, _), value)
            in zip(self.structure, data)
        }

    def decode(self, data: bytes) -> _DecodedMsgType:
        packet_type = get_devp2p_cmd_id(data)
        if packet_type != self.cmd_id:
            raise ValueError("Wrong packet type: {}".format(packet_type))
        return self.decode_payload(data[1:])

    def encode(self, data: _DecodedMsgType) -> Tuple[bytes, bytes]:
        payload = self.encode_payload(data)
        enc_cmd_id = rlp.encode(self.cmd_id, sedes=rlp.sedes.big_endian_int)
        frame_size = len(enc_cmd_id) + len(payload)
        if frame_size.bit_length() > 24:
            raise ValueError("Frame size has to fit in a 3-byte integer")

        # Drop the first byte as, per the spec, frame_size must be a 3-byte int.
        header = struct.pack('>I', frame_size)[1:]
        header = _pad_to_16_byte_boundary(header)

        body = _pad_to_16_byte_boundary(enc_cmd_id + payload)
        return header, body


class Protocol:
    logger = logging.getLogger("p2p.protocol.Protocol")
    name = None  # type: bytes
    version = None  # type: int
    cmd_length = None  # type: int
    # List of Command classes that this protocol supports.
    _commands = []  # type: List[Type[Command]]

    def __init__(self, peer: 'BasePeer', cmd_id_offset: int) -> None:
        self.peer = peer
        self.cmd_id_offset = cmd_id_offset
        self.commands = [cmd_class(self) for cmd_class in self._commands]
        self.cmd_by_id = dict((cmd.cmd_id, cmd) for cmd in self.commands)

    def send(self, header: bytes, body: bytes) -> None:
        self.peer.send(header, body)

    def __repr__(self):
        return "(%s, %d)" % (self.name.decode('ascii'), self.version)


def _pad_to_16_byte_boundary(data):
    """Pad the given data with NULL_BYTE up to the next 16-byte boundary."""
    remainder = len(data) % 16
    if remainder != 0:
        data += NULL_BYTE * (16 - remainder)
    return data
