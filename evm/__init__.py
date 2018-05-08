import pkg_resources
import sys

from evm.utils.logging import (
    setup_trace_logging
)

#
#  Setup TRACE level logging.
#
# This needs to be done before the other imports
setup_trace_logging()

from evm.chains import (  # noqa: F401
    Chain,
    MainnetChain,
    MainnetTesterChain,
    RopstenChain,
)

#
#  Ensure we can reach 1024 frames of recursion
#
sys.setrecursionlimit(1024 * 10)


__version__ = pkg_resources.get_distribution("py-evm").version
