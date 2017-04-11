import logging
import sys

from evm.utils.logging import (
    trace,
    TRACE_LEVEL_NUM,
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
