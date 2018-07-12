from concurrent.futures import ProcessPoolExecutor
import logging
import os
import rlp
import time
from typing import (
    Union,
)

from eth.exceptions import (
    ValidationError,
)
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
        cpu_count = os_cpu_count - 1
    return ProcessPoolExecutor(cpu_count)


class ThroughputTracker:
    """
    Tracks throughput using an exponential moving average.
    https://en.wikipedia.org/wiki/Moving_average#Exponential_moving_average
    """
    def __init__(self, default_throughput: Union[int, float], smoothing_factor: float) -> None:
        self._last_start: float = None
        self._throughput = float(default_throughput)
        if 0 < smoothing_factor < 1:
            self._alpha = smoothing_factor
        else:
            raise ValidationError("Smoothing factor of ThroughputTracker must be between 0 and 1")

    def begin_work(self) -> None:
        if self._last_start is not None:
            raise ValidationError("Cannot start the ThroughputTracker again without completing it")
        self._last_start = time.perf_counter()

    def complete_work(self, work_completed: Union[int, float]) -> None:
        if self._last_start is None:
            raise ValidationError("Cannot end the ThroughputTracker without starting it")
        time_elapsed = time.perf_counter() - self._last_start
        last_throughput = work_completed / time_elapsed
        self._throughput = (self._throughput * (1 - self._alpha)) + (last_throughput * self._alpha)
        self._last_start = None

    def get_throughput(self) -> float:
        return self._throughput
