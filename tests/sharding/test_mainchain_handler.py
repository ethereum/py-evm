import pytest

from viper import compiler

from eth_tester.backends.pyevm.main import get_default_account_keys

from evm.utils.address import generate_contract_address

import eth_utils

from evm.chains.sharding.mainchain_handler.vmc_utils import (
    decode_contract_call_result,
    mk_contract_tx_obj,
)

from evm.chains.sharding.mainchain_handler.mainchain_handler import (
    MainchainHandler,
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

@pytest.fixture
def chain_handler():
    return MainchainHandler(use_eth_tester=True)

def test_tester_chain_handler(chain_handler):
    chain_handler.mine(1)
    bytecode = compiler.compile(code)
    abi = compiler.mk_full_signature(code)
    sender_addr = test_keys[0].public_key.to_checksum_address()
    contract_addr = eth_utils.to_checksum_address(
        generate_contract_address(
            eth_utils.to_canonical_address(sender_addr),
            chain_handler.get_nonce(sender_addr)
        )
    )
    chain_handler.unlock_account(sender_addr, PASSPHRASE)
    tx_hash = chain_handler.deploy_contract(bytecode, sender_addr)
    chain_handler.mine(1)
    receipt = chain_handler.get_transaction_receipt(tx_hash)
    # notice: `contractAddress` in web3.py, but `contract_address` in eth_tester
    assert ('contractAddress' in receipt) and (contract_addr == receipt['contractAddress'])
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
    chain_handler.unlock_account(sender_addr, PASSPHRASE)
    tx_hash = chain_handler.send_transaction(tx_obj)
    chain_handler.mine(1)

    tx_obj = mk_contract_tx_obj('get_num_test', [], contract_addr, abi, sender_addr, 0, 50000, 1)
    result = chain_handler.call(tx_obj)
    decoded_result = decode_contract_call_result('get_num_test', abi, result)
    assert decoded_result == 4
