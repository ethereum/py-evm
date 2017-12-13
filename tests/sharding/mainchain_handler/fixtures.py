import pytest

from web3 import (
    Web3,
    HTTPProvider,
)

from web3.providers.eth_tester import EthereumTesterProvider

from eth_tester import EthereumTester

from eth_tester.backends.pyevm import PyEVMBackend

from evm.chains.sharding.mainchain_handler.config import (
    DEFAULT_RPC_SERVER_URL,
)

from evm.chains.sharding.mainchain_handler.mainchain_handler import (
    MainchainHandler,
)

@pytest.fixture
def mainchain_handler():
    # TODO: currently we only test with `TesterChainHandler` because it takes time to test with
    #       real RPC.
    #       Should see if there is a better way to test with RPCHandler.(maybe mock web3.py?)
    eth_tester = EthereumTester(
        backend=PyEVMBackend(),
        auto_mine_transactions=False,
    )
    provider = EthereumTesterProvider(eth_tester)
    # provider = HTTPProvider(DEFAULT_RPC_SERVER_URL)
    web3_instance = Web3(provider)
    return MainchainHandler(web3_instance, use_eth_tester=True)
