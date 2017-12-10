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

    def __init__(self, rpc_server_url=DEFAULT_RPC_SERVER_URL):
        self._w3 = Web3(HTTPProvider(rpc_server_url))

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
        :param privkey: bytes
        """
        self._w3.personal.importRawKey(privkey, passphrase)

    def mine(self, number):
        expected_block_number = self.get_block_number() + number
        self._w3.miner.start(1)
        while self.get_block_number() < expected_block_number:
            time.sleep(0.1)
        self._w3.miner.stop()

    def unlock_account(self, account, passphrase=PASSPHRASE):
        account = to_checksum_address(account)
        self._w3.personal.unlockAccount(account, passphrase)

    def get_transaction_receipt(self, tx_hash):
        # TODO: should unify the result from `web3.py` and `eth_tester`,
        #       dict.keys() returned from `web3.py` are camel style, while `eth_tester` are not
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
        tx_hash = self._w3.eth.sendRawTransaction(raw_tx_hex)
        return tx_hash
