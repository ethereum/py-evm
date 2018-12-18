import sys

import pkg_resources

from trinity import __version__


def construct_trinity_client_identifier() -> str:
    """
    Constructs the client identifier string

    e.g. 'Trinity/v1.2.3/darwin-amd64/python3.6.5'
    """
    return (
        "Trinity/"
        f"{__version__}/"
        f"{sys.platform}/"
        f"{sys.implementation.name}"
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )


def is_prerelease() -> bool:
    try:
        distro = pkg_resources.get_distribution("trinity")
        # mypy thinks that parsed_version is a tuple. Ignored...
        return distro.parsed_version.is_prerelease  # type: ignore
    except pkg_resources.DistributionNotFound:
        return True
