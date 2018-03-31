import pytest

from eth_tester.exceptions import (
    TransactionFailed,
)

from evm.constants import (
    ZERO_ADDRESS,
)

from evm.utils.hexadecimal import (
    encode_hex,
)

from evm.vm.forks.sharding.constants import (
    GENESIS_COLLATION_HASH,
)
from evm.vm.forks.sharding.shard_tracker import (
    NextLogUnavailable,
    ShardTracker,
)
from evm.vm.forks.sharding.vmc_handler import (
    mk_build_transaction_detail,
    mk_contract_tx_detail,
)

from tests.sharding.fixtures import (  # noqa: F401
    add_header_constant_call,
    default_shard_id,
    default_validator_index,
    mine,
    mk_colhdr_chain,
    mk_testing_colhdr,
    send_withdraw_tx,
    shard_tracker,
    vmc,
    vmc_handler,
)


def test_mk_build_transaction_detail():  # noqa: F811
    # test `mk_build_transaction_detail` ######################################
    build_transaction_detail = mk_build_transaction_detail(
        nonce=0,
        gas=10000,
    )
    assert 'nonce' in build_transaction_detail
    assert 'gas' in build_transaction_detail
    assert 'chainId' in build_transaction_detail
    with pytest.raises(ValueError):
        build_transaction_detail = mk_build_transaction_detail(
            nonce=None,
            gas=10000,
        )
    with pytest.raises(ValueError):
        build_transaction_detail = mk_build_transaction_detail(
            nonce=0,
            gas=None,
        )


def test_mk_contract_tx_detail():  # noqa: F811
    # test `mk_contract_tx_detail` ######################################
    tx_detail = mk_contract_tx_detail(
        sender_address=ZERO_ADDRESS,
        gas=21000,
    )
    assert 'from' in tx_detail
    assert 'gas' in tx_detail
    with pytest.raises(ValueError):
        tx_detail = mk_contract_tx_detail(
            sender_address=ZERO_ADDRESS,
            gas=None,
        )
    with pytest.raises(ValueError):
        tx_detail = mk_contract_tx_detail(
            sender_address=None,
            gas=21000,
        )


# TODO: should separate the tests into pieces, and do some refactors
def test_vmc_and_shard_tracker_contract_calls(vmc):  # noqa: F811
    # test `add_header` ######################################
    # create a testing collation header, whose parent is the genesis
    shard_tracker0 = shard_tracker(vmc, default_shard_id)
    header0_1 = mk_testing_colhdr(vmc, default_shard_id, GENESIS_COLLATION_HASH, 1)
    # if a header is added before its parent header is added, `add_header` should fail
    # TransactionFailed raised when assertions fail
    with pytest.raises(TransactionFailed):
        header_parent_not_added = mk_testing_colhdr(
            vmc,
            default_shard_id,
            header0_1.hash,
            1,
        )
        add_header_constant_call(vmc, header_parent_not_added)
    # when a valid header is added, the `add_header` call should succeed
    vmc.add_header(header0_1)
    mine(vmc, vmc.config['PERIOD_LENGTH'])
    # if a header is added before, the second trial should fail
    with pytest.raises(TransactionFailed):
        add_header_constant_call(vmc, header0_1)
    # when a valid header is added, the `add_header` call should succeed
    header0_2 = mk_testing_colhdr(vmc, default_shard_id, header0_1.hash, 2)
    vmc.add_header(header0_2)
    mine(vmc, vmc.config['PERIOD_LENGTH'])
    # confirm the score of header1 and header2 are correct or not
    colhdr0_1_score = vmc.functions.get_collation_header_score(
        default_shard_id,
        header0_1.hash,
    ).call(vmc.mk_default_contract_tx_detail())
    assert colhdr0_1_score == 1
    colhdr0_2_score = vmc.functions.get_collation_header_score(
        default_shard_id,
        header0_2.hash,
    ).call(vmc.mk_default_contract_tx_detail())
    assert colhdr0_2_score == 2
    # assert parent_hashes
    assert vmc.get_collation_parent_hash(default_shard_id, header0_1.hash) == GENESIS_COLLATION_HASH
    assert vmc.get_collation_parent_hash(default_shard_id, header0_2.hash) == header0_1.hash
    # confirm the logs are correct
    assert shard_tracker0.get_next_log()['score'] == 2
    assert shard_tracker0.get_next_log()['score'] == 1
    with pytest.raises(NextLogUnavailable):
        shard_tracker0.get_next_log()

    # filter logs in multiple shards
    shard_tracker1 = shard_tracker(vmc, 1)
    header1_1 = mk_testing_colhdr(vmc, 1, GENESIS_COLLATION_HASH, 1)
    vmc.add_header(header1_1)
    mine(vmc, vmc.config['PERIOD_LENGTH'])
    header0_3 = mk_testing_colhdr(vmc, default_shard_id, header0_2.hash, 3)
    vmc.add_header(header0_3)
    mine(vmc, vmc.config['PERIOD_LENGTH'])
    assert shard_tracker0.get_next_log()['score'] == 3
    # ensure that `get_next_log(0)` does not affect `get_next_log(1)`
    assert shard_tracker1.get_next_log()['score'] == 1
    logs = vmc.web3.eth.getLogs({
        "fromBlock": 0,
        "toBlock": vmc.web3.eth.blockNumber,
        "topics": [
            encode_hex(ShardTracker.COLLATION_ADDED_TOPIC),
        ]
    })
    assert len(logs) == 4

    # test `withdraw` ######################################
    send_withdraw_tx(vmc, default_validator_index)
    mine(vmc, 1)
    # if the only validator withdraws, because there is no validator anymore, the result of
    # `get_num_validators` must be 0.
    num_validators = vmc.functions.num_validators().call(vmc.mk_default_contract_tx_detail())
    assert num_validators == 0
