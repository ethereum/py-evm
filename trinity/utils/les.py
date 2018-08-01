import os

from eth_utils import big_endian_to_int


def gen_request_id() -> int:
    return big_endian_to_int(os.urandom(8))
