# Address utilities
from __future__ import absolute_import

import re

from .encoding import (
    encode_hex,
    decode_hex,
)
from .string import (
    coerce_args_to_text,
    coerce_args_to_bytes,
    coerce_return_to_text,
    coerce_return_to_bytes,
)
from .types import (
    is_string,
)
from .formatting import (
    add_0x_prefix,
    is_prefixed,
)


@coerce_args_to_text
def is_hex_address(value):
    """
    Checks if the given string is an address
    """

    if not is_string(value):
        return False
    elif len(value) not in {42, 40}:
        return False
    elif re.match(r"^(0x)?[0-9a-fA-F]{40}", value):
        return True
    else:
        return False


@coerce_args_to_bytes
def is_binary_address(value):
    """
    Checks if the given string is an address
    """

    if not is_string(value):
        return False
    elif len(value) != 20:
        return False
    else:
        return True


@coerce_args_to_text
def is_32byte_address(value):
    if not is_string(value):
        return False

    if len(value) == 32:
        value_as_hex = encode_hex(value)
    elif len(value) in {66, 64}:
        value_as_hex = add_0x_prefix(value)
    else:
        return False

    if is_prefixed(value_as_hex, '0x000000000000000000000000'):
        return True
    else:
        return False


@coerce_args_to_text
def is_address(value):
    if is_hex_address(value):
        return True
    elif is_binary_address(value):
        return True
    elif is_32byte_address(value):
        return True
    else:
        return False


@coerce_args_to_text
@coerce_return_to_text
def normalize_hex_address(address):
    return add_0x_prefix(address).lower()


@coerce_args_to_text
@coerce_return_to_text
def normalize_binary_address(address):
    hex_address = encode_hex(address)
    return normalize_hex_address(hex_address)


@coerce_args_to_text
@coerce_return_to_text
def normalize_32byte_address(address):
    if len(address) == 32:
        return normalize_binary_address(address[-20:])
    elif len(address) in {66, 64}:
        return normalize_hex_address(address[-40:])
    else:
        raise ValueError("Invalid address.  Must be 32 byte value")


@coerce_args_to_text
@coerce_return_to_text
def normalize_address(address):
    """
    Transforms given string to valid 20 bytes-length addres with 0x prefix
    """

    if is_hex_address(address):
        return normalize_hex_address(address)
    elif is_binary_address(address):
        return normalize_binary_address(address)
    elif is_32byte_address(address):
        return normalize_32byte_address(address)

    raise ValueError("Unknown address format")


def is_normalized_address(value):
    if not is_address(value):
        return False
    else:
        return value == normalize_address(value)


@coerce_args_to_bytes
@coerce_return_to_bytes
def canonicalize_address(address):
    return decode_hex(normalize_address(address))


def is_canonical_address(value):
    if not is_address(value):
        return False
    else:
        return value == canonicalize_address(value)


@coerce_args_to_text
def is_same_address(left, right):
    """
    Checks if both addresses are same or not
    """
    if not is_address(left) or not is_address(right):
        raise ValueError("Both values must be valid addresses")
    else:
        return normalize_address(left) == normalize_address(right)
