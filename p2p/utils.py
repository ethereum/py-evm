from concurrent.futures import ProcessPoolExecutor
import logging
import os
import rlp
from typing import Iterator

from eth_utils import to_tuple

from eth.constants import UINT_256_MAX
from eth.utils.numeric import big_endian_to_int


def sxor(s1: bytes, s2: bytes) -> bytes:
    if len(s1) != len(s2):
        raise ValueError("Cannot sxor strings of different length")
    return bytes(x ^ y for x, y in zip(s1, s2))


def roundup_16(x: int) -> int:
    """Rounds up the given value to the next multiple of 16."""
    remainder = x % 16
    if remainder != 0:
        x += 16 - remainder
    return x


def gen_request_id() -> int:
    return big_endian_to_int(os.urandom(8))


def get_devp2p_cmd_id(msg: bytes) -> int:
    """Return the cmd_id for the given devp2p msg.

    The cmd_id, also known as the payload type, is always the first entry of the RLP, interpreted
    as an integer.
    """
    return rlp.decode(msg[:1], sedes=rlp.sedes.big_endian_int)


@to_tuple
def sequence_builder(start_number: int, max_length: int, skip: int, reverse: bool) -> Iterator[int]:
    if reverse:
        step = -1 * (skip + 1)
    else:
        step = skip + 1

    cutoff_number = start_number + step * max_length

    for number in range(start_number, cutoff_number, step):
        if number < 0 or number > UINT_256_MAX:
            return
        else:
            yield number


def get_process_pool_executor() -> ProcessPoolExecutor:
    # Use CPU_COUNT - 1 processes to make sure we always leave one CPU idle so that it can run
    # asyncio's event loop.
    os_cpu_count = os.cpu_count()
    if os_cpu_count in (None, 0):
        # Need this because os.cpu_count() returns None when the # of CPUs is indeterminable.
        logger = logging.getLogger('p2p.utils')
        logger.warning(
            f"Could not determine number of CPUs, defaulting to 1 instead of {os_cpu_count}"
        )
        cpu_count = 1
    else:
        cpu_count = max(1, os_cpu_count - 1)
    return ProcessPoolExecutor(cpu_count)
