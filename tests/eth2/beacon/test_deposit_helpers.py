import ssz

from eth2._utils.merkle.common import (
    get_merkle_proof,
)
from eth2._utils.merkle.sparse import (
    calc_merkle_tree_from_leaves,
    get_merkle_root,
)
from eth2.beacon._utils.hash import (
    hash_eth2,
)

from eth2.beacon.deposit_helpers import (
    add_pending_validator,
    process_deposit,
)
from eth2.beacon.types.forks import Fork
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.validator_records import ValidatorRecord
from eth2.beacon.types.deposits import Deposit

from eth2.beacon.tools.builder.validator import (
    create_mock_deposit_data,
)


def test_add_pending_validator(sample_beacon_state_params,
                               sample_validator_record_params):

    validator_registry_len = 2
    state = BeaconState(**sample_beacon_state_params).copy(
        validator_registry=[
            ValidatorRecord(**sample_validator_record_params)
            for _ in range(validator_registry_len)
        ],
        validator_balances=(100,) * validator_registry_len,
    )
    validator = ValidatorRecord(**sample_validator_record_params)
    amount = 5566
    state = add_pending_validator(
        state,
        validator,
        amount,
    )

    assert state.validator_registry[-1] == validator


def test_process_deposit(config,
                         slots_per_epoch,
                         deposit_contract_tree_depth,
                         sample_beacon_state_params,
                         keymap,
                         pubkeys,
                         max_deposit_amount):
    state = BeaconState(**sample_beacon_state_params).copy(
        slot=1,
        validator_registry=(),
    )

    validator_index = 0
    pubkey_1 = pubkeys[0]
    amount = max_deposit_amount
    withdrawal_credentials = b'\x34' * 32
    fork = Fork(
        previous_version=config.GENESIS_FORK_VERSION.to_bytes(4, 'little'),
        current_version=config.GENESIS_FORK_VERSION.to_bytes(4, 'little'),
        epoch=config.GENESIS_EPOCH,
    )
    deposit_data = create_mock_deposit_data(
        config=config,
        pubkeys=pubkeys,
        keymap=keymap,
        validator_index=validator_index,
        withdrawal_credentials=withdrawal_credentials,
        fork=fork,
    )

    item = hash_eth2(ssz.encode(deposit_data))
    test_deposit_data_leaves = (item,)
    tree = calc_merkle_tree_from_leaves(test_deposit_data_leaves)
    root = get_merkle_root(test_deposit_data_leaves)
    proof = list(get_merkle_proof(tree, item_index=validator_index))

    state = state.copy(
        latest_eth1_data=state.latest_eth1_data.copy(
            deposit_root=root,
        ),
    )

    deposit = Deposit(
        proof=proof,
        index=validator_index,
        deposit_data=deposit_data,
    )

    # Add the first validator
    result_state = process_deposit(
        state=state,
        deposit=deposit,
        slots_per_epoch=slots_per_epoch,
        deposit_contract_tree_depth=deposit_contract_tree_depth,
    )

    assert len(result_state.validator_registry) == 1
    validator = result_state.validator_registry[validator_index]
    assert validator.pubkey == pubkey_1
    assert validator.withdrawal_credentials == withdrawal_credentials
    assert result_state.validator_balances[validator_index] == amount
    # test immutable
    assert len(state.validator_registry) == 0
