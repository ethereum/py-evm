import sys
import math

from toolz import (
    partial,
)

from evm.constants import (
    UINT_255_MAX,
    UINT_256_CEILING,
)

from eth_utils import (
    encode_hex,
    pad_left,
)


if sys.version_info.major == 2:
    import struct

    def int_to_big_endian(value):
        cs = []
        while value > 0:
            cs.append(chr(value % 256))
            value /= 256
        s = ''.join(reversed(cs))
        return s

    def big_endian_to_int(value):
        if len(value) == 1:
            return ord(value)
        elif len(value) <= 8:
            return struct.unpack('>Q', value.rjust(8, '\x00'))[0]
        else:
            return int(encode_hex(value), 16)
else:
    def int_to_big_endian(value):
        byte_length = math.ceil(value.bit_length() / 8)
        return (value).to_bytes(byte_length, byteorder='big')

    def big_endian_to_int(value):
        return int.from_bytes(value, byteorder='big')


def integer_to_32bytes(value):
    value_as_bytes = int_to_big_endian(value)
    padded_value_as_bytes = pad_left(value_as_bytes, 32, b'\x00')
    return padded_value_as_bytes


def ceilXX(value, ceiling):
    remainder = value % ceiling
    if remainder == 0:
        return value
    else:
        return value + ceiling - remainder


ceil32 = partial(ceilXX, ceiling=32)
ceil8 = partial(ceilXX, ceiling=8)


def unsigned_to_signed(value):
    if value <= UINT_255_MAX:
        return value
    else:
        return value - UINT_256_CEILING


def signed_to_unsigned(value):
    if value < 0:
        return value + UINT_256_CEILING
    else:
        return value
