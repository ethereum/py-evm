import pytest

from cytoolz.dicttoolz import (
    assoc,
)

from viper import compiler

from web3 import (
    Web3,
)

from web3.providers.eth_tester import (
    EthereumTesterProvider,
)

from eth_tester import (
    EthereumTester,
)

from eth_tester.backends.pyevm import (
    PyEVMBackend,
)

from eth_tester.backends.pyevm.main import (
    get_default_account_keys,
)

from evm.vm.forks.sharding.log_handler import (
    LogHandler,
)

code = """
Test: __log__({amount1: num})

counter: public(num)

@public
def __init__():
    self.counter = 0

@public
def emit_log():
    log.Test(self.counter)
    self.counter += 1
"""

test_keys = get_default_account_keys()
privkey = test_keys[0]


def take_snapshot(w3):
    snapshot_id = w3.testing.snapshot()
    return snapshot_id


def revert_to_snapshot(w3, snapshot_id):
    w3.testing.revert(snapshot_id)


def mine(w3, num_blocks):
    w3.testing.mine(num_blocks)


@pytest.fixture
def contract():
    eth_tester = EthereumTester(
        backend=PyEVMBackend(),
        auto_mine_transactions=False,
    )
    provider = EthereumTesterProvider(eth_tester)
    w3 = Web3(provider)
    bytecode = compiler.compile(code)
    abi = compiler.mk_full_signature(code)
    default_tx_detail = {'from': privkey.public_key.to_checksum_address(), 'gas': 500000}
    tx_hash = w3.eth.sendTransaction(assoc(default_tx_detail, 'data', bytecode))
    mine(w3, 1)
    receipt = w3.eth.getTransactionReceipt(tx_hash)
    contract_address = receipt['contractAddress']
    return w3.eth.contract(contract_address, abi=abi, bytecode=bytecode)


def test_log_handler_get_recent_block_hashes(contract):
    w3 = contract.web3
    default_tx_detail = {'from': privkey.public_key.to_checksum_address(), 'gas': 500000}
    assert contract.call(default_tx_detail).get_counter() == 0
    log_handler = LogHandler(w3)
    block = w3.eth.getBlock('latest')
    assert block['hash'] == log_handler.recent_block_hashes[-1]
    # snapshot when blockNumber=1
    snapshot_id = take_snapshot(w3)
    current_block_number = w3.eth.blockNumber
    # counter == 0 in block2
    contract.transact(default_tx_detail).emit_log()
    mine(w3, 1)
    block2 = w3.eth.getBlock('latest')
    revoked_hashes, new_block_hashes = log_handler.check_chain_head()
    assert block2['hash'] in new_block_hashes

    assert contract.call(default_tx_detail).get_counter() == 1
    revert_to_snapshot(w3, snapshot_id)
    assert w3.eth.blockNumber == current_block_number
    mine(w3, 1)  # block2_prime
    block2_prime = w3.eth.getBlock('latest')
    # counter == 1 in block3_prime
    contract.transact(default_tx_detail).emit_log()
    mine(w3, 1)
    block3_prime = w3.eth.getBlock('latest')
    # counter == 2 in block4_prime
    contract.transact(default_tx_detail).emit_log()
    mine(w3, 1)
    block4_prime = w3.eth.getBlock('latest')
    assert block4_prime['hash'] == log_handler.get_recent_block_hashes()[-1]
    revoked_hashes, new_block_hashes = log_handler.check_chain_head()
    assert block2['hash'] in revoked_hashes
    assert block2_prime['hash'] in new_block_hashes
    assert block3_prime['hash'] in new_block_hashes
    assert block4_prime['hash'] in new_block_hashes
