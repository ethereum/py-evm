import itertools

import pytest

from cytoolz.dicttoolz import (
    assoc,
)

from web3 import (
    Web3,
)

from web3.providers.eth_tester import (
    EthereumTesterProvider,
)

from eth_utils import (
    encode_hex,
    event_signature_to_log_topic,
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

@public
def emit_log(log_number: num):
    log.Test(log_number)
"""
abi = [{'name': 'Test', 'inputs': [{'type': 'int128', 'name': 'amount1', 'indexed': False}], 'anonymous': False, 'type': 'event'}, {'name': 'emit_log', 'outputs': [], 'inputs': [{'type': 'int128', 'name': 'log_number'}], 'constant': False, 'payable': False, 'type': 'function'}]  # noqa: E501
bytecode = b'a\x00\xf9V`\x005`\x1cRt\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00` Ro\x7f\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff`@R\x7f\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00``Rt\x01*\x05\xf1\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xfd\xab\xf4\x1c\x00`\x80R\x7f\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xd5\xfa\x0e\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00`\xa0Rc\xd0(}7`\x00Q\x14\x15a\x00\xf4W` `\x04a\x01@74\x15\x15XW``Q`\x045\x80`@Q\x90\x13XW\x80\x91\x90\x12XWPa\x01@Qa\x01`R\x7f\xaeh\x04lU;\x85\xd0\x8bolL6\x92S)\x06\xf3M\x1d\xa6\xcb\x032\x1e\xd6\x96\xca\x0b\xdcL\xad` a\x01`\xa1\x00[[a\x00\x04a\x00\xf9\x03a\x00\x04`\x009a\x00\x04a\x00\xf9\x03`\x00\xf3'  # noqa: E501

test_keys = get_default_account_keys()
privkey = test_keys[0]
default_tx_detail = {
    'from': privkey.public_key.to_checksum_address(),
    'gas': 500000,
}
test_event_signature = event_signature_to_log_topic("Test(int128)")


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
    tx_hash = w3.eth.sendTransaction(assoc(default_tx_detail, 'data', bytecode))
    mine(w3, 1)
    receipt = w3.eth.getTransactionReceipt(tx_hash)
    contract_address = receipt['contractAddress']
    return w3.eth.contract(contract_address, abi=abi, bytecode=bytecode)


def test_log_handler_preprocess_block_param(contract):
    log_handler = LogHandler(contract.web3)
    current_block_number = contract.web3.eth.blockNumber
    assert log_handler.preprocess_block_param(1) == 1
    assert log_handler.preprocess_block_param('earliest') == 0
    assert log_handler.preprocess_block_param('latest') == current_block_number
    assert log_handler.preprocess_block_param('pending') == current_block_number + 1
    block_hash = '0x1111111111111111111111111111111111111111111111111111111111111111'
    assert log_handler.preprocess_block_param(block_hash) == block_hash


def test_log_handler_mk_filter_params(contract):
    log_handler = LogHandler(contract.web3)
    filter_params = log_handler.mk_filter_params(1, 2)
    assert 'fromBlock' in filter_params
    assert 'toBlock' in filter_params
    filter_params_with_address = log_handler.mk_filter_params(1, 2, contract.address)
    assert contract.address == filter_params_with_address['address']
    topics = [encode_hex(test_event_signature)]
    filter_params_with_address = log_handler.mk_filter_params(1, 2, contract.address, topics)
    assert topics == filter_params_with_address['topics']


def test_log_handler_get_recent_block_hashes(contract):
    w3 = contract.web3
    log_handler = LogHandler(w3)
    block0 = w3.eth.getBlock(0)
    block1 = w3.eth.getBlock(1)
    recent_block_hashes = log_handler.get_recent_block_hashes()
    assert len(recent_block_hashes) == 2
    assert block0['hash'] == recent_block_hashes[0]
    assert block1['hash'] == recent_block_hashes[1]
    mine(w3, 2)
    block2 = w3.eth.getBlock(2)
    block3 = w3.eth.getBlock(3)
    recent_block_hashes = log_handler.get_recent_block_hashes()
    assert len(recent_block_hashes) == 4
    assert block2['hash'] == recent_block_hashes[2]
    assert block3['hash'] == recent_block_hashes[3]


def test_log_handler_check_chain_head_without_forks(contract):
    w3 = contract.web3
    log_handler = LogHandler(w3)
    revoked_hashes, new_block_hashes = log_handler.check_chain_head()
    assert revoked_hashes == tuple()
    assert new_block_hashes == tuple()
    mine(w3, 1)
    block2 = w3.eth.getBlock('latest')
    revoked_hashes, new_block_hashes = log_handler.check_chain_head()
    assert revoked_hashes == tuple()
    assert len(new_block_hashes) == 1
    assert block2['hash'] in new_block_hashes

    mine(w3, 3)
    block3 = w3.eth.getBlock(3)
    block4 = w3.eth.getBlock(4)
    block5 = w3.eth.getBlock(5)
    revoked_hashes, new_block_hashes = log_handler.check_chain_head()
    assert revoked_hashes == tuple()
    assert len(new_block_hashes) == 3
    assert block3['hash'] == new_block_hashes[0]
    assert block4['hash'] == new_block_hashes[1]
    assert block5['hash'] == new_block_hashes[2]


def test_log_handler_check_chain_head_with_forks(contract):
    w3 = contract.web3
    log_handler = LogHandler(w3)
    counter = itertools.count()
    block = w3.eth.getBlock('latest')
    assert block['hash'] == log_handler.recent_block_hashes[-1]
    # snapshot when blockNumber=1
    snapshot_id = take_snapshot(w3)
    current_block_number = w3.eth.blockNumber
    # counter == 0 in block2
    contract.transact(default_tx_detail).emit_log(next(counter))
    mine(w3, 1)
    block2 = w3.eth.getBlock('latest')
    revoked_hashes, new_block_hashes = log_handler.check_chain_head()
    assert revoked_hashes == tuple()
    assert block2['hash'] in new_block_hashes

    revert_to_snapshot(w3, snapshot_id)
    assert w3.eth.blockNumber == current_block_number
    mine(w3, 1)  # block2_prime
    block2_prime = w3.eth.getBlock('latest')
    # counter == 1 in block3_prime
    contract.transact(default_tx_detail).emit_log(next(counter))
    mine(w3, 1)
    block3_prime = w3.eth.getBlock('latest')
    # counter == 2 in block4_prime
    contract.transact(default_tx_detail).emit_log(next(counter))
    mine(w3, 1)
    block4_prime = w3.eth.getBlock('latest')
    assert block4_prime['hash'] == log_handler.get_recent_block_hashes()[-1]
    revoked_hashes, new_block_hashes = log_handler.check_chain_head()
    assert block2['hash'] in revoked_hashes
    assert len(revoked_hashes) == 1
    # ensure that the block in the behind of new_block_hashes is newer
    assert block2_prime['hash'] == new_block_hashes[-3]
    assert block3_prime['hash'] == new_block_hashes[-2]
    assert block4_prime['hash'] == new_block_hashes[-1]


def test_log_handler_filter_logs_without_forks(contract):
    w3 = contract.web3
    log_handler = LogHandler(w3)
    counter = itertools.count()
    contract.transact(default_tx_detail).emit_log(next(counter))
    mine(w3, 1)
    filter_params = log_handler.mk_filter_params(2, 2)
    logs = log_handler.filter_logs(filter_params)
    assert int(logs[0]['data'], 16) == 0
    contract.transact(default_tx_detail).emit_log(next(counter))
    mine(w3, 1)
    filter_params = log_handler.mk_filter_params(3, 3)
    logs = log_handler.filter_logs(filter_params)
    assert int(logs[0]['data'], 16) == 1
    # filter in range
    filter_params = log_handler.mk_filter_params(2, 3)
    logs = log_handler.filter_logs(filter_params)
    assert len(logs) == 2
    assert int(logs[0]['data'], 16) == 0
    assert int(logs[1]['data'], 16) == 1


def test_log_handler_filter_logs_with_forks(contract):
    w3 = contract.web3
    log_handler = LogHandler(w3)
    counter = itertools.count()
    snapshot_id = take_snapshot(w3)
    current_block_number = w3.eth.blockNumber
    contract.transact(default_tx_detail).emit_log(next(counter))
    mine(w3, 1)
    revert_to_snapshot(w3, snapshot_id)
    assert w3.eth.blockNumber == current_block_number
    contract.transact(default_tx_detail).emit_log(next(counter))
    mine(w3, 1)
    contract.transact(default_tx_detail).emit_log(next(counter))
    mine(w3, 1)
    filter_params = log_handler.mk_filter_params(2, 3)
    logs = log_handler.filter_logs(filter_params)
    # assert len(logs) == 2
    assert int(logs[0]['data'], 16) == 1
    assert int(logs[1]['data'], 16) == 2


def test_log_handler_get_new_logs_without_forks(contract):
    w3 = contract.web3
    log_handler = LogHandler(w3)
    counter = itertools.count()
    contract.transact(default_tx_detail).emit_log(next(counter))
    mine(w3, 1)
    logs_block2 = log_handler.get_new_logs(address=contract.address)
    assert len(logs_block2) == 1
    assert int(logs_block2[0]['data'], 16) == 0
    assert log_handler.get_new_logs() == tuple()
    contract.transact(default_tx_detail).emit_log(next(counter))
    mine(w3, 1)
    logs_block3 = log_handler.get_new_logs(address=contract.address)
    assert len(logs_block3) == 1
    assert int(logs_block3[0]['data'], 16) == 1
    assert log_handler.get_new_logs() == tuple()
    contract.transact(default_tx_detail).emit_log(next(counter))
    mine(w3, 1)
    contract.transact(default_tx_detail).emit_log(next(counter))
    mine(w3, 1)
    logs_block4_5 = log_handler.get_new_logs(address=contract.address)
    assert len(logs_block4_5) == 2
    assert int(logs_block4_5[0]['data'], 16) == 2
    assert int(logs_block4_5[1]['data'], 16) == 3
    assert log_handler.get_new_logs() == tuple()


def test_log_handler_get_new_logs_with_forks(contract):
    w3 = contract.web3
    log_handler = LogHandler(w3)
    counter = itertools.count()
    snapshot_id = take_snapshot(w3)
    current_block_number = w3.eth.blockNumber
    contract.transact(default_tx_detail).emit_log(next(counter))
    mine(w3, 1)
    revert_to_snapshot(w3, snapshot_id)
    assert w3.eth.blockNumber == current_block_number
    contract.transact(default_tx_detail).emit_log(next(counter))
    mine(w3, 1)
    contract.transact(default_tx_detail).emit_log(next(counter))
    mine(w3, 1)
    logs = log_handler.get_new_logs()
    # assert len(logs) == 2
    assert int(logs[0]['data'], 16) == 1
    assert int(logs[1]['data'], 16) == 2
    assert log_handler.get_new_logs() == tuple()
