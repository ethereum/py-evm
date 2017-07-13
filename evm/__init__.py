import logging
import sys
import os

from evm.utils.logging import (
    trace,
    TRACE_LEVEL_NUM,
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
    EVM,
    VM,
)

# Chooses which backend to use for the elliptic curve cryptography
os.environ['EVM_ECC_BACKEND_CLASS'] = \
    'evm.ecc.backends.pure_python_ecc_backend.PurePythonECCBackend'
