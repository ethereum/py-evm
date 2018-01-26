import logging
import pkg_resources
import sys

from evm.utils.logging import (
    trace,
    TRACE_LEVEL_NUM,
)

from evm.vm import (  # noqa: F401
    VM,
)
from evm.chains import (  # noqa: F401
    Chain,
    MainnetChain,
    MainnetTesterChain,
    RopstenChain,
)

#
#  Setup TRACE level logging.
#
logging.addLevelName(TRACE_LEVEL_NUM, 'TRACE')
logging.TRACE = TRACE_LEVEL_NUM
logging.Logger.trace = trace


#
#  Ensure we can reach 1024 frames of recursion
#
sys.setrecursionlimit(1024 * 10)


__version__ = pkg_resources.get_distribution("py-evm").version
