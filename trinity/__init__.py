import pkg_resources

# TODO: update this to use the `trinity` version once extracted from py-evm
try:
    __version__: str = pkg_resources.get_distribution("trinity").version
except pkg_resources.DistributionNotFound:
    # mypy doesn't like that `__version__` is defined twice
    __version__: str = pkg_resources.get_distribution("py-evm").version  # type: ignore

from .main import (  # noqa: F401
    main,
)
