import pkg_resources
import sys

# TODO: update this to use the `trinity` version once extracted from py-evm
__version__: str
try:
    __version__ = pkg_resources.get_distribution("trinity").version
except pkg_resources.DistributionNotFound:
    __version__ = "eth-{0}".format(
        pkg_resources.get_distribution("py-evm").version,
    )

# This is to ensure we call setup_trace_logging() before anything else.
import eth as _eth_module  # noqa: F401


def is_uvloop_supported() -> bool:
    return sys.platform in {'darwin', 'linux'} or sys.platform.startswith('freebsd')


if is_uvloop_supported():
    # Set `uvloop` as the default event loop
    import asyncio  # noqa: E402
    # TODO: drop "warnings" wrapper once issue is resolved in underlying modules
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', category=ImportWarning)
        import uvloop  # noqa: E402

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

from .main import (  # noqa: F401
    main,
)
