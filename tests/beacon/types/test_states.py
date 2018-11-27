import pytest

import rlp

from eth.constants import (
    ZERO_HASH32,
)
from eth.beacon.types.states import (
    BeaconState,
)
from eth.beacon.types.crosslink_records import (
    CrosslinkRecord,
)
from eth.utils.blake import (
    blake,
)

# from tests.beacon.helpers import (
#     mock_validator_record,
# )


@pytest.fixture
def empty_beacon_state():
    return BeaconState(
        validator_set_change_slot=0,
        validators=(),
        crosslinks=(),
        last_state_recalculation_slot=0,
        last_finalized_slot=0,
        last_justified_slot=0,
        justified_streak=0,
        shard_and_committee_for_slots=(),
        persistent_committees=(),
        persistent_committee_reassignments=(),
        next_shuffling_seed=ZERO_HASH32,
        deposits_penalized_in_period=(),
        validator_set_delta_hash_chain=ZERO_HASH32,
        current_exit_seq=00,
        genesis_time=00,
        processed_pow_receipt_root=ZERO_HASH32,
        candidate_pow_receipt_roots=(),
        pre_fork_version=0,
        post_fork_version=0,
        fork_slot_number=0,
        pending_attestations=(),
        recent_block_hashes=(),
        randao_mix=ZERO_HASH32,
    )


def test_defaults(sample_beacon_state_params):
    state = BeaconState(**sample_beacon_state_params)
    assert state.validator_set_change_slot == \
        sample_beacon_state_params['validator_set_change_slot']
    assert state.validators == sample_beacon_state_params['validators']


@pytest.mark.xfail(reason="Need to be fixed when helper function is updated")
@pytest.mark.parametrize(
    'expected', [(0), (1), (5)]
)
def test_num_validators(expected,
                        deposit_size,
                        default_end_dynasty,
                        empty_crystallized_state):
    validators = [
        mock_validator_record(
            pubkey,
            deposit_size,
            default_end_dynasty,
            start_dynasty=0,
        )
        for pubkey in range(expected)
    ]
    crystallized_state = empty_crystallized_state.copy(
        validators=validators,
    )

    assert crystallized_state.num_validators == expected


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
        crosslinks=crosslink_records,
    )

    assert state.num_crosslinks == expected


def test_hash(sample_beacon_state_params):
    state = BeaconState(**sample_beacon_state_params)
    assert state.hash == blake(rlp.encode(state))
