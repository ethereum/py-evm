import asyncio
import os

# TODO: use the eth-utils version of this.
from eth.utils.module_loading import import_string


def get_network():
    if 'DEVP2P_NETWORK' in os.environ:
        network = import_string(os.environ['DEVP2P_NETWORK'])
        return network
    else:
        return asyncio
