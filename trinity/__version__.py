import pkg_resources


# TODO: update to trinity package when it gets split out.
__version__ = pkg_resources.get_distribution("py-evm").version
