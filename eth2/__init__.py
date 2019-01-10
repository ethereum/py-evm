import pkg_resources

from eth.tools.logging import (
    setup_extended_logging
)

#
#  Setup TRACE level logging.
#
# This needs to be done before the other imports
setup_extended_logging()


__version__ = pkg_resources.get_distribution("py-evm").version
