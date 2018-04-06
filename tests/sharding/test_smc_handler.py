import logging

import pytest


from eth_tester.exceptions import (
    TransactionFailed,
)

from eth_tester.backends.pyevm.main import (
    get_default_account_keys,
)

from eth_utils import (
    is_address,
    to_checksum_address,
    encode_hex,
)

from evm.rlp.headers import (
    CollationHeader,
)
from evm.vm.forks.sharding.smc_handler import (
    make_call_context,
    make_transaction_context,
)
from evm.vm.forks.sharding.log_handler import (
    LogHandler,
)
from evm.vm.forks.sharding.shard_tracker import (
    COLLATION_ADDED_TOPIC,
    NextLogUnavailable,
    ShardTracker,
)

from tests.sharding.fixtures import (  # noqa: F401
    add_header_constant_call,
    make_testing_colhdr,
    smc_handler,
)
from tests.sharding.web3_utils import (
    mine,
)


GENESIS_COLHDR_HASH = b'\x00' * 32
ZERO_ADDR = b'\x00' * 20

test_keys = get_default_account_keys()

logger = logging.getLogger('evm.chain.sharding.mainchain_handler.SMCHandler')


def test_make_transaction_context():
    transaction_context = make_transaction_context(
        nonce=0,
        gas=10000,
    )
    assert 'nonce' in transaction_context
    assert 'gas' in transaction_context
    assert 'chainId' in transaction_context
    with pytest.raises(ValueError):
        transaction_context = make_transaction_context(
            nonce=None,
            gas=10000,
        )
    with pytest.raises(ValueError):
        transaction_context = make_transaction_context(
            nonce=0,
            gas=None,
        )


def test_make_call_context():
    call_context = make_call_context(
        sender_address=ZERO_ADDR,
        gas=1000,
    )
    assert 'from' in call_context
    assert 'gas' in call_context
    with pytest.raises(ValueError):
        call_context = make_call_context(
            sender_address=ZERO_ADDR,
            gas=None,
        )
    with pytest.raises(ValueError):
        call_context = make_call_context(
            sender_address=None,
            gas=1000,
        )


def test_smc_contract_calls(smc_handler):  # noqa: F811
    web3 = smc_handler.web3
    shard_id = 0
    validator_index = 0
    primary_key = test_keys[validator_index]
    primary_addr = primary_key.public_key.to_canonical_address()
    default_gas = smc_handler.config['DEFAULT_GAS']

    shard_0_tracker = ShardTracker(shard_id, LogHandler(web3), smc_handler.address)

    lookahead_blocks = (
        smc_handler.config['LOOKAHEAD_PERIODS'] * smc_handler.config['PERIOD_LENGTH']
    )
    # test `deposit` and `get_eligible_proposer` ######################################
    # now we require 1 validator.
    # if there is currently no validator, we deposit one.
    # else, there should only be one validator, for easier testing.
    num_validators = smc_handler.call(
        make_call_context(sender_address=primary_addr, gas=default_gas)
    ).num_validators()
    if num_validators == 0:
        # deposit as the first validator
        smc_handler.deposit()
        # TODO: error occurs when we don't mine so many blocks
        mine(web3, lookahead_blocks)
        assert smc_handler.get_eligible_proposer(shard_id) == smc_handler.sender_address

    # assert the current_block_number >= LOOKAHEAD_PERIODS * PERIOD_LENGTH
    # to ensure that `get_eligible_proposer` works
    current_block_number = web3.eth.blockNumber
    if current_block_number < lookahead_blocks:
        mine(web3, lookahead_blocks - current_block_number)
    assert web3.eth.blockNumber >= lookahead_blocks

    num_validators = smc_handler.call(
        make_call_context(sender_address=primary_addr, gas=default_gas)
    ).num_validators()
    assert num_validators == 1
    assert smc_handler.get_eligible_proposer(shard_id) != ZERO_ADDR
    logger.debug("smc_handler.num_validators()=%s", num_validators)

    # test `add_header` ######################################
    # create a testing collation header, whose parent is the genesis
    header0_1 = make_testing_colhdr(smc_handler, shard_id, GENESIS_COLHDR_HASH, 1)
    # if a header is added before its parent header is added, `add_header` should fail
    # TransactionFailed raised when assertions fail
    with pytest.raises(TransactionFailed):
        header_parent_not_added = make_testing_colhdr(
            smc_handler,
            shard_id,
            header0_1.hash,
            1,
        )
        add_header_constant_call(smc_handler, header_parent_not_added)
    # when a valid header is added, the `add_header` call should succeed
    smc_handler.add_header(header0_1)
    mine(web3, smc_handler.config['PERIOD_LENGTH'])
    # if a header is added before, the second trial should fail
    with pytest.raises(TransactionFailed):
        add_header_constant_call(smc_handler, header0_1)
    # when a valid header is added, the `add_header` call should succeed
    header0_2 = make_testing_colhdr(smc_handler, shard_id, header0_1.hash, 2)
    smc_handler.add_header(header0_2)

    mine(web3, smc_handler.config['PERIOD_LENGTH'])
    # confirm the score of header1 and header2 are correct or not
    colhdr0_1_score = smc_handler.call(
        make_call_context(sender_address=primary_addr, gas=default_gas)
    ).get_collation_header_score(shard_id, header0_1.hash)
    assert colhdr0_1_score == 1
    colhdr0_2_score = smc_handler.call(
        make_call_context(sender_address=primary_addr, gas=default_gas)
    ).get_collation_header_score(shard_id, header0_2.hash)
    assert colhdr0_2_score == 2
    # confirm the logs are correct
    assert shard_0_tracker.get_next_log()['score'] == 2
    assert shard_0_tracker.get_next_log()['score'] == 1
    with pytest.raises(NextLogUnavailable):
        shard_0_tracker.get_next_log()

    # filter logs in multiple shards
    shard_1_tracker = ShardTracker(1, LogHandler(web3), smc_handler.address)
    header1_1 = make_testing_colhdr(smc_handler, 1, GENESIS_COLHDR_HASH, 1)
    smc_handler.add_header(header1_1)
    mine(web3, 1)
    header0_3 = make_testing_colhdr(smc_handler, shard_id, header0_2.hash, 3)
    smc_handler.add_header(header0_3)
    mine(web3, 1)
    assert shard_0_tracker.get_next_log()['score'] == 3
    assert shard_1_tracker.get_next_log()['score'] == 1
    logs = web3.eth.getLogs({
        "fromBlock": 0,
        "toBlock": web3.eth.blockNumber,
        "topics": [
            encode_hex(COLLATION_ADDED_TOPIC),
        ]
    })
    assert len(logs) == 4

    # test `withdraw` ######################################
    smc_handler.withdraw(validator_index)
    mine(web3, 1)
    # if the only validator withdraws, because there is no validator anymore, the result of
    # `num_validators` must be 0.
    num_validators = smc_handler.call(
        make_call_context(sender_address=primary_addr, gas=default_gas)
    ).num_validators()
    assert num_validators == 0
