from viper import compiler

from eth_tester import EthereumTester

from eth_tester.backends.pyevm import PyEVMBackend

from eth_tester.backends.pyevm.main import get_default_account_keys

from evm.utils.address import generate_contract_address

import eth_utils

from config import (
    GASPRICE,
    PASSPHRASE,
    TX_GAS,
)

from chain_handler import (
    BaseChainHandler,
    RPCChainHandler,
)

from vmc_utils import (
    decode_contract_call_result,
    mk_contract_tx_obj,
)

keys = get_default_account_keys()

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
        return self.et.get_nonce(address)

    def import_privkey(self, privkey, passphrase=PASSPHRASE):
        self.et.add_account(privkey, passphrase)

    def mine(self, number):
        self.et.mine_blocks(num_blocks=number)

    def unlock_account(self, account, passphrase=PASSPHRASE):
        # self.et.unlock_account(account, passphrase)
        pass

    def get_transaction_receipt(self, tx_hash):
        return self.et.get_transaction_receipt(tx_hash)

    def send_transaction(self, tx_obj):
        return self.et.send_transaction(tx_obj)

    def call(self, tx_obj):
        return self.et.call(tx_obj)

    # utils

    def send_tx(self, sender_addr, to=None, value=0, data=b'', gas=TX_GAS, gas_price=GASPRICE):
        tx_obj = {
            'from': sender_addr,
            'value': value,
            'gas': gas,
            'gas_price': gas_price,
            'data': eth_utils.encode_hex(data),
        }
        if to is not None:
            tx_obj['to'] = to
        self.unlock_account(sender_addr)
        tx_hash = self.send_transaction(tx_obj)
        return tx_hash

    def deploy_contract(self, bytecode, address, value=0, gas=TX_GAS, gas_price=GASPRICE):
        return self.send_tx(address, value=value, data=bytecode, gas=gas, gas_price=gas_price)

    def direct_tx(self, tx):
        return self.et.backend.chain.apply_transaction(tx)

def test_contract(ChainHandlerClass):
    chain_handler = ChainHandlerClass()
    chain_handler.mine(1)
    code = """
num_test: public(num)

@public
def __init__():
    self.num_test = 42

@public
def update_num_test(_num_test: num):
    self.num_test = _num_test
"""
    bytecode = compiler.compile(code)
    abi = compiler.mk_full_signature(code)
    sender_addr = keys[0].public_key.to_checksum_address()
    contract_addr = eth_utils.address.to_checksum_address(
        generate_contract_address(
            eth_utils.to_canonical_address(sender_addr),
            chain_handler.get_nonce(sender_addr)
        )
    )
    tx_hash = chain_handler.deploy_contract(bytecode, sender_addr)
    chain_handler.mine(1)
    assert contract_addr == chain_handler.get_transaction_receipt(tx_hash)['contract_address']
    tx_obj = mk_contract_tx_obj('get_num_test', [], contract_addr, abi, sender_addr, 0, 50000, 1)
    result = chain_handler.call(tx_obj)
    decoded_result = decode_contract_call_result('get_num_test', abi, result)
    assert decoded_result == 42
    # tx_hash = chain_handler.send_transaction(tx_obj)
    chain_handler.mine(1)

    tx_obj = mk_contract_tx_obj(
        'update_num_test',
        [4],
        contract_addr,
        abi,
        sender_addr,
        0,
        50000,
        1,
    )
    tx_hash = chain_handler.send_transaction(tx_obj)
    chain_handler.mine(1)

    tx_obj = mk_contract_tx_obj('get_num_test', [], contract_addr, abi, sender_addr, 0, 50000, 1)
    result = chain_handler.call(tx_obj)
    decoded_result = decode_contract_call_result('get_num_test', abi, result)
    assert decoded_result == 4

if __name__ == '__main__':
    # test_contract(RPCChainHandler)
    test_contract(TesterChainHandler)
