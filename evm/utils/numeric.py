import functools
import math
import sys

from evm.constants import (
    UINT_255_MAX,
    UINT_256_CEILING,
)


if sys.version_info.major == 2:
    import struct
    import codecs
    import binascii

    def int_to_big_endian(value):
        if value == 0:
            return b'\x00'

        value_as_hex = (hex(value)[2:]).rstrip('L')

        if len(value_as_hex) % 2:
            return binascii.unhexlify('0' + value_as_hex)
        else:
            return binascii.unhexlify(value_as_hex)

    def big_endian_to_int(value):
        if len(value) == 1:
            return ord(value)
        elif len(value) <= 8:
            return struct.unpack('>Q', value.rjust(8, '\x00'))[0]
        else:
            return int(codecs.encode(value, 'hex'), 16)

    int_to_byte = chr
    byte_to_int = ord
else:
    def int_to_big_endian(value):
        byte_length = math.ceil(value.bit_length() / 8)
        return (value).to_bytes(byte_length, byteorder='big')

    def big_endian_to_int(value):
        return int.from_bytes(value, byteorder='big')

    def int_to_byte(value):
        return bytes([value])

    byte_to_int = ord


def ceilXX(value, ceiling):
    remainder = value % ceiling
    if remainder == 0:
        return value
    else:
        return value + ceiling - remainder


ceil32 = functools.partial(ceilXX, ceiling=32)
ceil8 = functools.partial(ceilXX, ceiling=8)


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


def safe_ord(value):
    if isinstance(value, int):
        return value
    else:
        return ord(value)
