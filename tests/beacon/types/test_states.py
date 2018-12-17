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
from eth.beacon.utils.hash import (
    hash_,
)

from tests.beacon.helpers import (
    mock_validator_record,
)


@pytest.fixture
def empty_beacon_state():
    return BeaconState(
        validator_registry=(),
        validator_registry_latest_change_slot=10,
        validator_registry_exit_count=10,
        validator_registry_delta_chain_tip=b'\x55' * 32,
        randao_mix=b'\x55' * 32,
        next_seed=b'\x55' * 32,
        shard_committees_at_slots=(),
        persistent_committees=(),
        persistent_committee_reassignments=(),
        previous_justified_slot=0,
        justified_slot=0,
        justification_bitfield=0,
        finalized_slot=0,
        latest_crosslinks=(),
        latest_state_recalculation_slot=0,
        latest_block_hashes=(),
        latest_penalized_exit_balances=(),
        latest_attestations=(),
        processed_pow_receipt_root=b'\x55' * 32,
        candidate_pow_receipt_roots=(),
        genesis_time=0,
        fork_data=ForkData(
            pre_fork_version=0,
            post_fork_version=0,
            fork_slot=0,
        ),
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
    validator_registry = [
        mock_validator_record(
            pubkey,
            max_deposit,
        )
        for pubkey in range(expected)
    ]
    state = empty_beacon_state.copy(
        validator_registry=validator_registry,
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
    assert state.hash == hash_(rlp.encode(state))
