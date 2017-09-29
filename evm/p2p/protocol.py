import logging
import struct

import rlp
from rlp import sedes

from evm.constants import NULL_BYTE


class Command:
    id = None
    decode_strict = True
    structure = []

    @classmethod
    def encode_payload(cls, data):
        if isinstance(data, dict):  # convert dict to ordered list
            if not isinstance(cls.structure, list):
                raise ValueError("Command.structure must be a list when data is a dict")
            expected_keys = sorted(name for name, _ in cls.structure)
            data_keys = sorted(data.keys())
            if data_keys != expected_keys:
                raise rlp.EncodingError(
                    "Keys in data dict ({}) do not match expected keys ({})".format(
                        data_keys, expected_keys))
            data = [data[name] for name, _ in cls.structure]
        if isinstance(cls.structure, sedes.CountableList):
            encoder = cls.structure
        else:
            encoder = sedes.List([type_ for _, type_ in cls.structure])
        return rlp.encode(data, sedes=encoder)

    @classmethod
    def decode_payload(cls, rlp_data):
        if isinstance(cls.structure, sedes.CountableList):
            decoder = cls.structure
        else:
            decoder = sedes.List(
                [type_ for _, type_ in cls.structure], strict=cls.decode_strict)
        data = rlp.decode(rlp_data, sedes=decoder)
        if isinstance(cls.structure, sedes.CountableList):
            return data
        else:
            return {
                field_name: value
                for ((field_name, _), value)
                in zip(cls.structure, data)
            }

    @classmethod
    def decode(cls, data):
        packet_type = rlp.decode(data[:1], sedes=sedes.big_endian_int)
        if packet_type != cls.id:
            raise ValueError("Wrong packet type: {}".format(packet_type))
        return cls.decode_payload(data[1:])

    @classmethod
    def encode(cls, data):
        payload = cls.encode_payload(data)
        enc_cmd_id = rlp.encode(cls.id, sedes=rlp.sedes.big_endian_int)
        frame_size = len(enc_cmd_id) + len(payload)
        if frame_size.bit_length() > 24:
            raise ValueError("Frame size has to fit in a 3-byte integer")

        # Drop the first byte as, per the spec, frame_size must be a 3-byte int.
        header = struct.pack('>I', frame_size)[1:]
        header = _pad_to_16_byte_boundary(header)

        body = _pad_to_16_byte_boundary(enc_cmd_id + payload)
        return header, body


class Protocol:
    logger = logging.getLogger("evm.p2p.protocol.Protocol")
    name = None
    version = None
    commands = []

    def __init__(self, peer):
        self.peer = peer
        self.cmd_by_id = dict((cmd.id, cmd) for cmd in self.commands)

    def process(self, cmd_id, msg):
        cmd = self.cmd_by_id[cmd_id]
        return cmd.handle(self, msg)

    def send(self, header, body):
        self.peer.send(header, body)


def _pad_to_16_byte_boundary(data):
    """Pad the given data with NULL_BYTE up to the next 16-byte boundary."""
    remainder = len(data) % 16
    if remainder != 0:
        data += NULL_BYTE * (16 - remainder)
    return data
