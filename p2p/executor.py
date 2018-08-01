import os
import logging
from concurrent.futures import Executor, ProcessPoolExecutor


def get_asyncio_executor() -> Executor:
    # Use CPU_COUNT - 1 processes to make sure we always leave one CPU idle so that it can run
    # asyncio's event loop.
    os_cpu_count = os.cpu_count()
    if os_cpu_count in (None, 0):
        # Need this because os.cpu_count() returns None when the # of CPUs is indeterminable.
        logger = logging.getLogger('p2p.executor')
        logger.warning(
            "Could not determine number of CPUs, defaulting to 1 instead of %s",
            os_cpu_count,
        )
        cpu_count = 1
    else:
        cpu_count = max(1, os_cpu_count - 1)
    return ProcessPoolExecutor(cpu_count)
