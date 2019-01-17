from trinity.db.chain import (
    AsyncChainDBPreProxy
)
from trinity.db.header import (
    AsyncHeaderDBPreProxy,
)


def test_can_instantiate_proxy():
    # The test fails if we forget to implement any of the abstract methods
    # that the proxy derives from it's abstract base classes
    assert AsyncHeaderDBPreProxy(None) is not None
    assert AsyncChainDBPreProxy(None) is not None
