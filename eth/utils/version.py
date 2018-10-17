import sys

from eth import __version__


def construct_evm_runtime_identifier() -> str:
    """
    Constructs the EVM runtime identifier string

    e.g. 'Py-EVM/v1.2.3/darwin-amd64/python3.6.5'
    """
    return "Py-EVM/{0}/{platform}/{imp.name}{v.major}.{v.minor}.{v.micro}".format(
        __version__,
        platform=sys.platform,
        v=sys.version_info,
        # mypy Doesn't recognize the `sys` module as having an `implementation` attribute.
        imp=sys.implementation,
    )
