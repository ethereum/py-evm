import pkg_resources

# TODO: update this to use the `trinity` version once extracted from py-evm
try:
    __version__: str = pkg_resources.get_distribution("trinity").version
except pkg_resources.DistributionNotFound:
    __version__: str = pkg_resources.get_distribution("py-evm").version

from .main import (  # noqa: F401
    main,
)
