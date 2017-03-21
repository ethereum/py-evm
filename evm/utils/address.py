from eth_utils import (
    pad_left,
)


def force_bytes_to_address(value):
    address = pad_left(value[-20:], 20, b'\x00')
    return address
