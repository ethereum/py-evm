from __future__ import absolute_import

import codecs

from sha3 import keccak_256

from .string import (
    coerce_args_to_text,
    force_bytes,
)
from .formatting import (
    remove_0x_prefix,
)


@coerce_args_to_text
def sha3(value, encoding=None):

    if encoding is None:
        value_to_hash = force_bytes(value)
    elif encoding == 'hex':
        value_to_hash = codecs.decode(remove_0x_prefix(value), encoding)
    else:
        raise ValueError("Unsupported Encoding")

    return keccak_256(value_to_hash).hexdigest()


# ensure we have the *right* sha3 installed
assert sha3('') == 'c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470'
