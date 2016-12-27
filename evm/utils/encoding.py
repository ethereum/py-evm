# String encodings and numeric representations
import codecs

from .types import (
    is_string,
)
from .string import (
    coerce_args_to_bytes,
    coerce_return_to_text,
    coerce_return_to_bytes,
)
from .formatting import (
    remove_0x_prefix,
    add_0x_prefix,
)


@coerce_return_to_bytes
def decode_hex(value):
    if not is_string(value):
        raise TypeError('Value must be an instance of str or unicode')
    return codecs.decode(remove_0x_prefix(value), 'hex')


@coerce_args_to_bytes
@coerce_return_to_text
def encode_hex(value):
    if not is_string(value):
        raise TypeError('Value must be an instance of str or unicode')
    return add_0x_prefix(codecs.encode(value, 'hex'))
