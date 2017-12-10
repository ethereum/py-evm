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

    def __init__(self):
        self.et = EthereumTester(backend=PyEVMBackend(), auto_mine_transactions=False)

    def get_block_by_number(self, block_number):
        block = self.et.get_block_by_number(block_number)
        return block

    def get_block_number(self):
        # raise CanonicalHeadNotFound if head is not found
        head_block_header = self.et.backend.chain.get_canonical_head()
        return head_block_header.block_number

    def get_nonce(self, address):
        address = to_checksum_address(address)
        return self.et.get_nonce(address)

    def import_privkey(self, privkey, passphrase=PASSPHRASE):
        """
        :param privkey: PrivateKey object from eth_keys
        """
        self.et.add_account(privkey.to_hex(), passphrase)

    def mine(self, number):
        self.et.mine_blocks(num_blocks=number)

    def unlock_account(self, account, passphrase=PASSPHRASE):
        account = to_checksum_address(account)
        # self.et.unlock_account(account, passphrase)
        pass

    def get_transaction_receipt(self, tx_hash):
        # TODO: should unify the result from `web3.py` and `eth_tester`,
        #       dict.keys() returned from `web3.py` are camel style, while `eth_tester` are not
        return self.et.get_transaction_receipt(tx_hash)

    def send_transaction(self, tx_obj):
        return self.et.send_transaction(tx_obj)

    def call(self, tx_obj):
        return self.et.call(tx_obj)

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
