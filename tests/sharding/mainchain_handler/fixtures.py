import pytest

import rlp

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

    def direct_tx(self, tx):
        raw_tx = rlp.encode(tx)
        raw_tx_hex = self.w3.toHex(raw_tx)
        tx_hash = self.w3.eth.sendRawTransaction(raw_tx_hex)
        return tx_hash


@pytest.fixture
def mainchain_handler():
    eth_tester = EthereumTester(
        backend=PyEVMBackend(),
        auto_mine_transactions=False,
    )
    provider = EthereumTesterProvider(eth_tester)
    w3 = Web3(provider)
    return TesterMainchainHandler(w3)
