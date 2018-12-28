import pytest

import rlp

from eth.beacon.types.fork_data import (
    ForkData,
)
from eth.beacon.types.states import (
    BeaconState,
)
from eth.beacon.types.crosslink_records import (
    CrosslinkRecord,
)
from eth.beacon._utils.hash import (
    hash_eth2,
)

from tests.beacon.helpers import (
    mock_active_validator_record,
)


@pytest.fixture
def empty_beacon_state():
    return BeaconState(
        slot=0,
        genesis_time=0,
        fork_data=ForkData(
            pre_fork_version=0,
            post_fork_version=0,
            fork_slot=0,
        ),
        validator_registry=(),
        validator_registry_latest_change_slot=10,
        validator_registry_exit_count=10,
        validator_registry_delta_chain_tip=b'\x55' * 32,
        latest_randao_mixes=(),
        latest_vdf_outputs=(),
        shard_committees_at_slots=(),
        persistent_committees=(),
        persistent_committee_reassignments=(),
        previous_justified_slot=0,
        justified_slot=0,
        justification_bitfield=0,
        finalized_slot=0,
        latest_crosslinks=(),
        latest_block_roots=(),
        latest_penalized_exit_balances=(),
        latest_attestations=(),
        batched_block_roots=(),
        processed_pow_receipt_root=b'\x55' * 32,
        candidate_pow_receipt_roots=(),
    )


@pytest.fixture()
def ten_validator_state(empty_beacon_state, sample_validator_record_params, max_deposit):
    validator_count = 10
    return empty_beacon_state.copy(
        validator_registry=tuple(
            mock_active_validator_record(
                pubkey,
            )
            for pubkey in range(validator_count)
        ),
        validator_balances=tuple(
            max_deposit
            for _ in range(validator_count)
        )
    )


def test_defaults(sample_beacon_state_params):
    state = BeaconState(**sample_beacon_state_params)
    assert state.validator_registry == sample_beacon_state_params['validator_registry']
    assert state.validator_registry_latest_change_slot == sample_beacon_state_params['validator_registry_latest_change_slot']  # noqa: E501


@pytest.mark.parametrize(
    'expected', [(0), (1)]
)
def test_num_validators(expected,
                        max_deposit,
                        empty_beacon_state):
    state = empty_beacon_state.copy(
        validator_registry=[
            mock_active_validator_record(
                pubkey,
            )
            for pubkey in range(expected)
        ],
        validator_balances=(
            max_deposit
            for _ in range(expected)
        )
    )

    assert state.num_validators == expected


@pytest.mark.parametrize(
    'expected', [(0), (1), (5)]
)
def test_num_crosslink_records(expected,
                               sample_crosslink_record_params,
                               empty_beacon_state):
    crosslink_records = [
        CrosslinkRecord(**sample_crosslink_record_params)
        for i in range(expected)
    ]
    state = empty_beacon_state.copy(
        latest_crosslinks=crosslink_records,
    )

    assert state.num_crosslinks == expected


def test_hash(sample_beacon_state_params):
    state = BeaconState(**sample_beacon_state_params)
    assert state.root == hash_eth2(rlp.encode(state))


@pytest.mark.parametrize(
    'validator_index, new_pubkey, new_balance',
    [
        (0, 5566, 100),
        (100, 5566, 100),
    ]
)
def test_update_validator(ten_validator_state, validator_index, new_pubkey, new_balance):
    state = ten_validator_state
    validator = mock_active_validator_record(new_pubkey)

    if validator_index < state.num_validators:
        result_state = state.update_validator(
            validator_index=validator_index,
            validator=validator,
            balance=new_balance,
        )
        assert result_state.validator_balances[validator_index] == new_balance
        assert result_state.validator_registry[validator_index].pubkey == new_pubkey
        assert state.validator_registry[validator_index].pubkey != new_pubkey
    else:
        with pytest.raises(IndexError):
            state.update_validator(
                validator_index=validator_index,
                validator=validator,
                balance=new_balance,
            )
