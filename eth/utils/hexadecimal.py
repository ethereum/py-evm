from __future__ import unicode_literals

import codecs


def encode_hex(value: bytes) -> str:
    return '0x' + codecs.decode(codecs.encode(value, 'hex'), 'utf8')    # type: ignore


def decode_hex(value: str) -> bytes:
    _, _, hex_part = value.rpartition('x')
    return codecs.decode(hex_part, 'hex')   # type: ignore
