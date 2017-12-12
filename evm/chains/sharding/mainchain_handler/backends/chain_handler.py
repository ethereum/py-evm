import time

import rlp

from web3 import (
    HTTPProvider,
    Web3,
)

from eth_utils import (
    to_checksum_address,
)

from evm.chains.sharding.mainchain_handler.config import (
    DEFAULT_RPC_SERVER_URL,
    GASPRICE,
    PASSPHRASE,
    TX_GAS,
)

from evm.chains.sharding.mainchain_handler.backends.base import (
    BaseChainHandler,
)

class RPCChainHandler(BaseChainHandler):

    def __init__(self, use_eth_tester=False, rpc_server_url=DEFAULT_RPC_SERVER_URL):
        self._use_eth_tester = use_eth_tester
        if use_eth_tester:
            from web3.providers.eth_tester import EthereumTesterProvider
            from eth_tester import EthereumTester
            from eth_tester.backends.pyevm import PyEVMBackend
            self._eth_tester = EthereumTester(
                backend=PyEVMBackend(),
                auto_mine_transactions=False,
            )
            provider = EthereumTesterProvider(self._eth_tester)
        else:
            provider = HTTPProvider(rpc_server_url)
        self._w3 = Web3(provider)
        assert self._w3.isConnected()

    # RPC related

    def get_block_by_number(self, block_number):
        return self._w3.eth.getBlock(block_number)

    def get_block_number(self):
        return self._w3.eth.blockNumber

    def get_code(self, address):
        address = to_checksum_address(address)
        return self._w3.eth.getCode(address)

    def get_nonce(self, address):
        address = to_checksum_address(address)
        return self._w3.eth.getTransactionCount(address)

    def import_privkey(self, privkey, passphrase=PASSPHRASE):
        """
        :param privkey: PrivateKey object from eth_keys
        """
        self._w3.personal.importRawKey(privkey.to_hex(), passphrase)


    def mine(self, number):
        if self._use_eth_tester:
            self.evm_mine(number)
        else:
            self.miner_mine(number)

    def miner_mine(self, number):
        expected_block_number = self.get_block_number() + number
        self._w3.miner.start(1)
        while self.get_block_number() < expected_block_number:
            time.sleep(0.1)
        self._w3.miner.stop()

    def evm_mine(self, number):
        # evm.mine
        self._w3.testing.mine(number)

    def unlock_account(self, account, passphrase=PASSPHRASE):
        account = to_checksum_address(account)
        self._w3.personal.unlockAccount(account, passphrase)

    def get_transaction_receipt(self, tx_hash):
        return self._w3.eth.getTransactionReceipt(tx_hash)

    def send_transaction(self, tx_obj):
        return self._w3.eth.sendTransaction(tx_obj)

    def call(self, tx_obj):
        return self._w3.eth.call(tx_obj)

    # utils

    def deploy_contract(self, bytecode, address, value=0, gas=TX_GAS, gas_price=GASPRICE):
        address = to_checksum_address(address)
        self.unlock_account(address)
        tx_hash = self.send_transaction({
            'from': address,
            'value': value,
            'gas': gas,
            'gas_price': gas_price,
            'data': bytecode,
        })
        return tx_hash

    def direct_tx(self, tx):
        raw_tx = rlp.encode(tx)
        raw_tx_hex = self._w3.toHex(raw_tx)
        try:
            tx_hash = self._w3.eth.sendRawTransaction(raw_tx_hex)
        except ValueError:
            # FIXME: if `sendRawTransaction` is not implemented, `ValueError` is raised
            #        In this situation, if we used `eth_tester`, try again directly with
            #        `self._eth_tester.backend.chain.apply_transaction`
            if self._use_eth_tester:
                return self._eth_tester.backend.chain.apply_transaction(tx)
        return tx_hash
