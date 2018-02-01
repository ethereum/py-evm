from __future__ import unicode_literals

import codecs


def encode_hex(value):
    return '0x' + codecs.decode(codecs.encode(value, 'hex'), 'utf8')


def decode_hex(value):
    _, _, hex_part = value.rpartition('x')
    return codecs.decode(hex_part, 'hex')
