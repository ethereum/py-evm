import pkg_resources

# TODO: update this to use the `trinity` version once extracted from py-evm
__version__ = pkg_resources.get_distribution("py-evm").version

from .main import (  # noqa: F401
    main,
)
