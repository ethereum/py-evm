import pytest

import rlp

from web3 import (
    Web3,
    # HTTPProvider,
)

from web3.providers.eth_tester import EthereumTesterProvider

from eth_tester import EthereumTester

from eth_tester.backends.pyevm import PyEVMBackend

# from evm.chains.sharding.mainchain_handler.config import (
#     DEFAULT_RPC_SERVER_URL,
# )

from evm.chains.sharding.mainchain_handler.mainchain_handler import (
    MainchainHandler,
)


class TesterMainchainHandler(MainchainHandler):
    def mine(self, number):
        self.w3.testing.mine(number)

    def direct_tx(self, tx):
        raw_tx = rlp.encode(tx)
        raw_tx_hex = self.w3.toHex(raw_tx)
        try:
            tx_hash = self.w3.eth.sendRawTransaction(raw_tx_hex)
        except ValueError:
            # FIXME: if `sendRawTransaction` is not implemented, `ValueError` is raised
            #        In this situation, if we used `eth_tester`, try again directly with
            #        `self._eth_tester.backend.chain.apply_transaction`
            tx_hash = self.w3.providers[0].ethereum_tester.backend.chain.apply_transaction(tx)
        return tx_hash


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
    # return MainchainHandler(web3_instance)
    return TesterMainchainHandler(web3_instance)
