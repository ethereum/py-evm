import logging
import struct
from abc import ABC, abstractmethod
from typing import (
    Any,
    cast,
    Dict,
    List,
    Tuple,
    Type,
    TYPE_CHECKING,
    Union,
)

import rlp
from rlp import sedes

from eth_utils import encode_hex

from eth_typing import BlockIdentifier, BlockNumber

from eth.constants import NULL_BYTE
from eth.rlp.headers import BlockHeader

from p2p.exceptions import ValidationError
from p2p.utils import get_devp2p_cmd_id


# Workaround for import cycles caused by type annotations:
# http://mypy.readthedocs.io/en/latest/common_issues.html#import-cycles
if TYPE_CHECKING:
    from p2p.peer import ChainInfo, BasePeer  # noqa: F401


_DecodedMsgType = Union[
    Dict[str, Any],
    List[rlp.Serializable],
    Tuple[rlp.Serializable, ...],
]


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
            self._logger = logging.getLogger(
                "p2p.protocol.{0}".format(self.__class__.__name__)
            )
        return self._logger

    @property
    def is_base_protocol(self) -> bool:
        return self.cmd_id_offset == 0

    def __str__(self) -> str:
        return "{} (cmd_id={})".format(self.__class__.__name__, self.cmd_id)

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
        # All clients seem to ignore frame header data, so we do the same, although I'm not sure
        # why geth uses the following value:
        # https://github.com/ethereum/go-ethereum/blob/master/p2p/rlpx.go#L556
        zero_header = b'\xc2\x80\x80'
        header += zero_header
        header = _pad_to_16_byte_boundary(header)

        body = _pad_to_16_byte_boundary(enc_cmd_id + payload)
        return header, body


class BaseRequest(ABC):
    """
    Base representation of a *request* to a connected peer which has a matching
    *response*.
    """
    @abstractmethod
    def validate_response(self, response: Any) -> None:
        pass


class BaseHeaderRequest(BaseRequest):
    block_number_or_hash: BlockIdentifier
    max_headers: int
    skip: int
    reverse: bool

    @property
    @abstractmethod
    def MAX_HEADERS_FETCH(self) -> int:
        pass

    def generate_block_numbers(self,
                               block_number: BlockNumber=None) -> Tuple[BlockNumber, ...]:
        if block_number is None and not self.is_numbered:
            raise TypeError(
                "A `block_number` must be supplied to generate block numbers "
                "for hash based header requests"
            )
        elif block_number is not None and self.is_numbered:
            raise TypeError(
                "The `block_number` parameter may not be used for number based "
                "header requests"
            )
        elif block_number is None:
            block_number = cast(BlockNumber, self.block_number_or_hash)

        max_headers = min(self.MAX_HEADERS_FETCH, self.max_headers)

        # inline import until this module is moved to `trinity`
        from trinity.utils.headers import sequence_builder
        return sequence_builder(
            block_number,
            max_headers,
            self.skip,
            self.reverse,
        )

    @property
    def is_numbered(self) -> bool:
        return isinstance(self.block_number_or_hash, int)

    def validate_headers(self,
                         headers: Tuple[BlockHeader, ...]) -> None:
        if not headers:
            # An empty response is always valid
            return
        elif not self.is_numbered:
            first_header = headers[0]
            if first_header.hash != self.block_number_or_hash:
                raise ValidationError(
                    "Returned headers cannot be matched to header request. "
                    "Expected first header to have hash of {0} but instead got "
                    "{1}.".format(
                        encode_hex(self.block_number_or_hash),
                        encode_hex(first_header.hash),
                    )
                )

        block_numbers: Tuple[BlockNumber, ...] = tuple(
            header.block_number for header in headers
        )
        return self.validate_sequence(block_numbers)

    def validate_sequence(self, block_numbers: Tuple[BlockNumber, ...]) -> None:
        if not block_numbers:
            return
        elif self.is_numbered:
            expected_numbers = self.generate_block_numbers()
        else:
            expected_numbers = self.generate_block_numbers(block_numbers[0])

        # check for numbers that should not be present.
        unexpected_numbers = set(block_numbers).difference(expected_numbers)
        if unexpected_numbers:
            raise ValidationError(
                'Unexpected numbers: {0}'.format(unexpected_numbers))

        # check that the numbers are correctly ordered.
        expected_order = tuple(sorted(
            block_numbers,
            reverse=self.reverse,
        ))
        if block_numbers != expected_order:
            raise ValidationError(
                'Returned headers are not correctly ordered.\n'
                'Expected: {0}\n'
                'Got     : {1}\n'.format(expected_order, block_numbers)
            )

        # check that all provided numbers are an ordered subset of the master
        # sequence.
        iter_expected = iter(expected_numbers)
        for number in block_numbers:
            for value in iter_expected:
                if value == number:
                    break
            else:
                raise ValidationError(
                    'Returned headers contain an unexpected block number.\n'
                    'Unexpected Number: {0}\n'
                    'Expected Numbers : {1}'.format(number, expected_numbers)
                )


class Protocol:
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
        self.cmd_by_id = dict((cmd.cmd_id, cmd) for cmd in self.commands)

    def send(self, header: bytes, body: bytes) -> None:
        self.peer.send(header, body)

    def __repr__(self) -> str:
        return "(%s, %d)" % (self.name, self.version)


class BaseBlockHeaders(ABC, Command):

    @abstractmethod
    def extract_headers(self, msg: _DecodedMsgType) -> Tuple[BlockHeader, ...]:
        raise NotImplementedError("Must be implemented by subclasses")


def _pad_to_16_byte_boundary(data: bytes) -> bytes:
    """Pad the given data with NULL_BYTE up to the next 16-byte boundary."""
    remainder = len(data) % 16
    if remainder != 0:
        data += NULL_BYTE * (16 - remainder)
    return data
