import struct
from typing import (
    Any,
    Callable,
    ClassVar,
    Type,
)

import snappy
import rlp
from eth_utils.toolz import identity

from p2p.abc import (
    CommandAPI,
    CompressionCodecAPI,
    MessageAPI,
    SerializationCodecAPI,
    TCommand,
)
from p2p.message import Message
from p2p.exceptions import MalformedMessage
from p2p.typing import TCommandPayload


#
# Serialization
#
class NoneSerializationCodec(SerializationCodecAPI[None]):
    def encode(self, payload: None) -> bytes:
        return b''

    def decode(self, data: bytes) -> None:
        if len(data) != 0:
            raise MalformedMessage("Should be empty")
        return None


class RLPCodec(SerializationCodecAPI[TCommandPayload]):
    decode_strict: bool

    def __init__(self,
                 sedes: Any,
                 decode_strict: bool = True,
                 process_outbound_payload_fn: Callable[[TCommandPayload], Any] = None,
                 process_inbound_payload_fn: Callable[[Any], TCommandPayload] = None) -> None:
        if not hasattr(sedes, 'serialize'):
            raise TypeError("Invalid sedes: ...")
        if not hasattr(sedes, 'deserialize'):
            raise TypeError("Invalid sedes: ...")

        self.decode_strict = decode_strict
        self.sedes = sedes

        self._process_outbound_payload_fn = process_outbound_payload_fn or identity
        self._process_inbound_payload_fn = process_inbound_payload_fn or identity

    def encode(self, payload: TCommandPayload) -> bytes:
        return rlp.encode(self._process_outbound_payload_fn(payload), sedes=self.sedes)

    def decode(self, data: bytes) -> TCommandPayload:
        return self._process_inbound_payload_fn(
            rlp.decode(data, strict=self.decode_strict, sedes=self.sedes, recursive_cache=True)
        )


#
# Compression
#
class SnappyCodec(CompressionCodecAPI):
    def compress(self, data: bytes) -> bytes:
        return snappy.compress(data)

    def decompress(self, data: bytes) -> bytes:
        return snappy.decompress(data)


class NoCompressionCodec(CompressionCodecAPI):
    def compress(self, data: bytes) -> bytes:
        return data

    def decompress(self, data: bytes) -> bytes:
        return data


HEADER_DATA = b'\xc2\x80\x80'  # rlp.encode([0, 0])
ZERO_16 = b'\x00' * 16


class BaseCommand(CommandAPI[TCommandPayload]):
    protocol_command_id: ClassVar[int]

    serialization_codec: SerializationCodecAPI[TCommandPayload]
    compression_codec: CompressionCodecAPI = SnappyCodec()

    payload: TCommandPayload

    def __init__(self, payload: TCommandPayload) -> None:
        self.payload = payload

    def encode(self, cmd_id: int, snappy_support: bool) -> MessageAPI:
        raw_payload_data = self.serialization_codec.encode(self.payload)

        if snappy_support:
            payload_data = self.compression_codec.compress(raw_payload_data)
        else:
            payload_data = raw_payload_data

        cmd_id_data = rlp.encode(cmd_id, sedes=rlp.sedes.big_endian_int)
        frame_size = len(cmd_id_data) + len(payload_data)

        if frame_size.bit_length() > 24:
            raise ValueError("Frame size has to fit in a 3-byte integer")

        # Frame-size is a 3-bit integer
        header = struct.pack('>I', frame_size)[1:] + HEADER_DATA
        body = cmd_id_data + payload_data

        return Message(header, body)

    @classmethod
    def decode(cls: Type[TCommand], message: MessageAPI, snappy_support: bool) -> TCommand:
        if snappy_support:
            payload_data = cls.compression_codec.decompress(message.body[1:])
        else:
            payload_data = message.body[1:]

        payload = cls.serialization_codec.decode(payload_data)
        return cls(payload)
