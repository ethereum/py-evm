import pytest

from web3 import (
    Web3,
)

from web3.providers.eth_tester import EthereumTesterProvider

from eth_tester import EthereumTester

from eth_tester.backends.pyevm import PyEVMBackend

from evm.chains.sharding.mainchain_handler.mainchain_handler import (
    MainchainHandler,
)


class TesterMainchainHandler(MainchainHandler):
    def mine(self, number):
        self.w3.testing.mine(number)


@pytest.fixture
def mainchain_handler():
    eth_tester = EthereumTester(
        backend=PyEVMBackend(),
        auto_mine_transactions=False,
    )
    provider = EthereumTesterProvider(eth_tester)
    w3 = Web3(provider)
    return TesterMainchainHandler(w3)
