from viper import compiler

from eth_tester.backends.pyevm.main import get_default_account_keys

import eth_utils

from evm.utils.address import generate_contract_address

from tests.sharding.mainchain_handler.fixtures import (
    mainchain_handler,
)


PASSPHRASE = '123'

test_keys = get_default_account_keys()

code = """
num_test: public(num)

@public
def __init__():
    self.num_test = 42

@public
def update_num_test(_num_test: num):
    self.num_test = _num_test
"""

def test_tester_chain_handler(mainchain_handler):
    mainchain_handler.mine(1)
    bytecode = compiler.compile(code)
    abi = compiler.mk_full_signature(code)
    sender_addr = test_keys[0].public_key.to_checksum_address()
    contract_addr = eth_utils.to_checksum_address(
        generate_contract_address(
            eth_utils.to_canonical_address(sender_addr),
            mainchain_handler.get_nonce(sender_addr)
        )
    )
    mainchain_handler.unlock_account(sender_addr, PASSPHRASE)
    tx_hash = mainchain_handler.deploy_contract(bytecode, sender_addr)
    mainchain_handler.mine(1)
    receipt = mainchain_handler.get_transaction_receipt(tx_hash)
    # notice: `contractAddress` in web3.py, but `contract_address` in eth_tester
    assert ('contractAddress' in receipt) and (contract_addr == receipt['contractAddress'])
    contract = mainchain_handler.contract(contract_addr, abi=abi, bytecode=bytecode)
    result = contract.call({'from': sender_addr, 'gas': 50000}).get_num_test()
    assert result == 42
    mainchain_handler.mine(1)

    mainchain_handler.unlock_account(sender_addr, PASSPHRASE)
    tx_hash = contract.transact({
        'from': sender_addr,
        'gas': 50000,
        'gas_price': 1,
    }).update_num_test(4)
    mainchain_handler.mine(1)

    result = contract.call({'from': sender_addr, 'gas': 50000}).get_num_test()
    assert result == 4
