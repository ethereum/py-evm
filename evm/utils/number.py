import sys
import math
import binascii
import struct

from .string import (
    coerce_return_to_bytes,
    coerce_args_to_bytes,
)
from .formatting import (
    pad_left,
)


if sys.version_info.major == 2:
    @coerce_return_to_bytes
    def integer_to_big_endian(lnum):
        if lnum == 0:
            return b'\0'
        s = hex(lnum)[2:]
        s = s.rstrip('L')
        if len(s) & 1:
            s = '0' + s
        s = binascii.unhexlify(s)
        return s

    @coerce_args_to_bytes
    def big_endian_to_integer(value):
        if len(value) == 1:
            return ord(value)
        elif len(value) <= 8:
            return struct.unpack('>Q', value.rjust(8, '\x00'))[0]
        else:
            return int(encode_hex(value), 16)
else:
    @coerce_return_to_bytes
    def integer_to_big_endian(value):
        byte_length = math.ceil(value.bit_length() / 8)
        return (value).to_bytes(byte_length, byteorder='big')

    @coerce_args_to_bytes
    def big_endian_to_integer(value):
        return int.from_bytes(value, byteorder='big')


UINT_256_MAX = 2**256 - 1


@coerce_args_to_bytes
@coerce_return_to_bytes
def integer_to_32bytes(value):
    bytes_value = integer_to_big_endian(value)
    return pad_left(bytes_value, 32, b'\x00')
