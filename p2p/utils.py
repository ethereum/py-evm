import datetime
from concurrent.futures import Executor, ProcessPoolExecutor
import logging
import os
from typing import Tuple

import rlp


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


def get_devp2p_cmd_id(msg: bytes) -> int:
    """Return the cmd_id for the given devp2p msg.

    The cmd_id, also known as the payload type, is always the first entry of the RLP, interpreted
    as an integer.
    """
    return rlp.decode(msg[:1], sedes=rlp.sedes.big_endian_int)


def time_since(start_time: datetime.datetime) -> Tuple[int, int, int, int]:
    delta = datetime.datetime.now() - start_time
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return delta.days, hours, minutes, seconds


CPU_EMPTY_VALUES = {None, 0}


def get_asyncio_executor(cpu_count: int=None) -> Executor:
    # Use CPU_COUNT - 1 processes to make sure we always leave one CPU idle so that it can run
    # asyncio's event loop.
    if cpu_count is None:
        os_cpu_count = os.cpu_count()
        if os_cpu_count in CPU_EMPTY_VALUES:
            # Need this because os.cpu_count() returns None when the # of CPUs is indeterminable.
            logger = logging.getLogger('p2p')
            logger.warning(
                "Could not determine number of CPUs, defaulting to 1 instead of %s",
                os_cpu_count,
            )
            cpu_count = 1
        else:
            cpu_count = max(1, os_cpu_count - 1)
    return ProcessPoolExecutor(cpu_count)
