import pkg_resources
import sys

from eth_utils import setup_DEBUG2_logging

#
#  Setup DEBUG2 level logging.
#
# This needs to be done before the other imports
setup_DEBUG2_logging()

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
