import sys

from importlib.metadata import (
    version as __version,
)

from eth.chains import (
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


__version__ = __version("py-evm")
