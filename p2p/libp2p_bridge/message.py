from enum import (
    Enum,
)

from eth_utils import (
    big_endian_to_int,
    int_to_big_endian,
)

from p2p.libp2p_bridge.constants import (
    INT_BYTES,
)


def int_to_bytes(value):
    if not isinstance(value, int):
        raise ValueError
    return bytes.rjust(int_to_big_endian(value), INT_BYTES, b'\x00')


def bytes_to_int(value):
    if not isinstance(value, bytes):
        raise ValueError("value should be bytes type")
    if len(value) != INT_BYTES:
        raise ValueError("len of bytes should be {}, instead of {}".format(INT_BYTES, len(value)))
    return big_endian_to_int(value.lstrip())


class BaseMessage:
    def to_bytes(self):
        raise NotImplementedError

    def from_bytes(self, b):
        raise NotImplementedError


class Collation(BaseMessage):
    shard_id = None
    period = None
    blobs = None

    def __init__(self, shard_id, period, blobs):
        self.shard_id = shard_id
        self.period = period
        self.blobs = blobs

    def to_bytes(self):
        return int_to_bytes(self.shard_id) + int_to_bytes(self.period) + self.blobs

    @classmethod
    def from_bytes(self, b):
        if len(b) < INT_BYTES * 2:
            raise ValueError("bytes too short for a collation: len={}".format(len(b)))
        return Collation(
            bytes_to_int(b[:INT_BYTES]),
            bytes_to_int(b[INT_BYTES:INT_BYTES * 2]),
            b[INT_BYTES * 2:],
        )


class CollationRequest(BaseMessage):
    shard_id = None
    period = None
    collation_hash = None

    def __init__(self, shard_id, period, collation_hash):
        self.shard_id = shard_id
        self.period = period
        self.collation_hash = collation_hash

    def to_bytes(self):
        return (
            int_to_bytes(self.shard_id) +
            int_to_bytes(self.period) +
            self.collation_hash.encode()
        )

    @classmethod
    def from_bytes(self, b):
        if len(b) < INT_BYTES * 2:
            raise ValueError("bytes too short for a collation: len={}".format(len(b)))
        return CollationRequest(
            bytes_to_int(b[:INT_BYTES]),
            bytes_to_int(b[INT_BYTES:INT_BYTES * 2]),
            b[INT_BYTES * 2:].decode(),
        )


class MsgType(Enum):
    Unknown = -1
    Collation = 2
    CollationRequest = 3
