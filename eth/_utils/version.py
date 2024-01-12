import sys

from eth import (
    __version__,
)


def construct_evm_runtime_identifier() -> str:
    """
    Constructs the EVM runtime identifier string

    e.g. 'Py-EVM/v1.2.3/darwin-amd64/python3.9.13'
    """
    platform = sys.platform
    v = sys.version_info
    imp = sys.implementation

    return f"Py-EVM/{__version__}/{platform}/{imp.name}{v.major}.{v.minor}.{v.micro}"
