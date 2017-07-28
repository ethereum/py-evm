import logging
import sys

from evm.utils.logging import (
    trace,
    TRACE_LEVEL_NUM,
)

from evm.chain import (  # noqa: F401
    Chain,
)

from .__version__ import (  # noqa: F401
    __title__,
    __description__,
    __url__,
    __version__,
    __copyright__,
    __author__,
    __author_email__,
    __license__,
    __build__
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


from evm.vm import (  # noqa: F401
    VM,
)
