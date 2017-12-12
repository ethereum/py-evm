import logging

from web3 import (
    Web3,
)

from web3.providers.eth_tester import (
    EthereumTesterProvider,
)

from eth_utils import (
    to_checksum_address,
)

from eth_tester import EthereumTester

from eth_tester.backends.pyevm import PyEVMBackend

from evm.utils.hexadecimal import (
    encode_hex,
)

from evm.chains.sharding.mainchain_handler.config import (
    GASPRICE,
    PASSPHRASE,
    TX_GAS,
)

from evm.chains.sharding.mainchain_handler.backends.base import (
    BaseChainHandler,
)

class TesterChainHandler(BaseChainHandler):

    logger = logging.getLogger("evm.chain.sharding.TesterChainHandler")

    def __init__(self):
        self.et = EthereumTester(backend=PyEVMBackend(), auto_mine_transactions=False)
        self._w3 = Web3(EthereumTesterProvider(self.et))

    def get_block_by_number(self, block_number):
        # block = self.et.get_block_by_number(block_number)
        block = self._w3.eth.getBlockByNumber(block_number)
        self.logger.debug("get_block_by_number(%s)=%s", block_number, block)
        return block

    def get_block_number(self):
        # raise CanonicalHeadNotFound if head is not found
        # head_block_header = self.et.backend.chain.get_canonical_head()
        head_block_number = self._w3.eth.blockNumber
        self.logger.debug("get_block_number()=%s", head_block_number)
        return head_block_number

    def get_nonce(self, address):
        address = to_checksum_address(address)
        nonce = self._w3.eth.getTransactionCount(address)
        self.logger.debug("get_nonce(%s)=%s", address, nonce)
        return nonce

    def import_privkey(self, privkey, passphrase=PASSPHRASE):
        """
        :param privkey: PrivateKey object from eth_keys
        """
        # self.et.add_account(privkey.to_hex(), passphrase)
        self._w3.personal.importRawKey(privkey.to_hex(), passphrase)

    def mine(self, number):
        # evm.mine
        self._w3.testing.mine(number)
        # self.et.mine_blocks(num_blocks=number)

    def unlock_account(self, account, passphrase=PASSPHRASE):
        account = to_checksum_address(account)
        # self.et.unlock_account(account, passphrase)
        self._w3.personal.unlockAccount(account, passphrase)

    def get_transaction_receipt(self, tx_hash):
        # TODO: should unify the result from `web3.py` and `eth_tester`,
        #       dict.keys() returned from `web3.py` are camel style, while `eth_tester` are not
        receipt = self._w3.eth.getTransactionReceipt(tx_hash)
        # receipt = self.et.get_transaction_receipt(tx_hash)
        if receipt is None:
            self.logger.debug("Receipt not found: tx_hash=%s", tx_hash)
            raise ValueError("Transaction {} is not found.".format(tx_hash))
        self.logger.debug("get_transaction_receipt(%s)=%s", tx_hash, receipt)
        return receipt

    def send_transaction(self, tx_obj):
        # tx_hash = self.et.send_transaction(tx_obj)
        tx_hash = self._w3.eth.sendTransaction(tx_obj)
        self.logger.debug("send_transaction(%s), hash=%s", tx_obj, tx_hash)
        return tx_hash

    def call(self, tx_obj):
        # result = self.et.call(tx_obj)
        result = self._w3.eth.call(tx_obj)
        self.logger.debug("call(%s), result=%s", tx_obj, result)
        return result

    # utils

    def send_tx(self, sender_addr, to=None, value=0, data=b'', gas=TX_GAS, gas_price=GASPRICE):
        sender_addr = to_checksum_address(sender_addr)
        tx_obj = {
            'from': sender_addr,
            'value': value,
            'gas': gas,
            'gas_price': gas_price,
            'data': encode_hex(data),
        }
        if to is not None:
            tx_obj['to'] = to
        self.unlock_account(sender_addr)
        tx_hash = self.send_transaction(tx_obj)
        return tx_hash

    def deploy_contract(self, bytecode, address, value=0, gas=TX_GAS, gas_price=GASPRICE):
        address = to_checksum_address(address)
        return self.send_tx(address, value=value, data=bytecode, gas=gas, gas_price=gas_price)

    def direct_tx(self, tx):
        return self.et.backend.chain.apply_transaction(tx)
