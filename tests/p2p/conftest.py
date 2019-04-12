import pytest

from p2p.tools.factories import (
    AddressFactory,
    DiscoveryProtocolFactory,
    NodeFactory,
    PrivateKeyFactory,
)


"""
# Uncomment the following lines to globally change the logging level for all
# `p2p` namespaced loggers.  Useful for debugging failing tests in async code
# when the only output you get is a timeout or something else which doens't
# indicate where things failed.
import pytest

@pytest.fixture(autouse=True, scope="session")
def p2p_logger():
    import logging
    import sys

    logger = logging.getLogger('p2p')

    handler = logging.StreamHandler(sys.stdout)

    # level = DEBUG2_LEVEL_NUM
    level = logging.DEBUG
    level = logging.INFO

    logger.setLevel(level)
    handler.setLevel(level)

    logger.addHandler(handler)

    return logger
"""


@pytest.fixture(autouse=True)
def _network_sim(router):
    network = router.get_network(name='simulated')
    with network.patch_asyncio():
        yield network


@pytest.fixture(scope='session')
def factories():
    class P2PFactories:
        AddressFactory = AddressFactory
        DiscoveryProtocolFactory = DiscoveryProtocolFactory
        NodeFactory = NodeFactory
        PrivateKeyFactory = staticmethod(PrivateKeyFactory)
    return P2PFactories()
