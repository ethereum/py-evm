from __future__ import unicode_literals

import codecs


def encode_hex(value):
    return '0x' + codecs.decode(codecs.encode(value, 'hex'), 'utf8')
