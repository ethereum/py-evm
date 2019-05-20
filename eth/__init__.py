import pkg_resources
import sys

from eth.tools.logging import (
    setup_extended_logging
)

#
#  Setup TRACE level logging.
#
# This needs to be done before the other imports
setup_extended_logging()

from eth.chains import (  # noqa: F401
    Chain,
    MainnetChain,
    MainnetTesterChain,
    RopstenChain,
)

#
#  Ensure we can reach 1024 frames of recursion
#
EVM_RECURSION_LIMIT = 1024 * 12
sys.setrecursionlimit(max(EVM_RECURSION_LIMIT, sys.getrecursionlimit()))


__version__ = pkg_resources.get_distribution("py-evm").version
