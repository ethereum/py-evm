import pytest

import rlp

from eth.constants import (
    ZERO_HASH32,
)
from eth.beacon.types.crystallized_states import (
    CrystallizedState,
)
from eth.beacon.types.crosslink_records import (
    CrosslinkRecord,
)
from eth.utils.blake import (
    blake,
)

from tests.beacon.helpers import (
    mock_validator_record,
)


@pytest.fixture
def empty_crystallized_state():
    return CrystallizedState(
        validators=None,
        last_state_recalc=0,
        shard_and_committee_for_slots=None,
        last_justified_slot=0,
        justified_streak=0,
        last_finalized_slot=0,
        current_dynasty=0,
        crosslink_records=None,
        dynasty_seed=ZERO_HASH32,
        dynasty_start=0,
    )


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
                               empty_crystallized_state):
    crosslink_records = [
        CrosslinkRecord(**sample_crosslink_record_params)
        for i in range(expected)
    ]
    crystallized_state = empty_crystallized_state.copy(
        crosslink_records=crosslink_records,
    )

    assert crystallized_state.num_crosslink_records == expected


@pytest.mark.parametrize(
    'num_active_validators',
    [
        (0),
        (1),
        (5),
        (20),
    ]
)
def test_total_deposits(num_active_validators, deposit_size, default_end_dynasty, empty_crystallized_state):
    start_dynasty = 10
    active_validators = [
        mock_validator_record(
            pubkey,
            deposit_size,
            default_end_dynasty,
            start_dynasty=start_dynasty,
        )
        for pubkey in range(num_active_validators)
    ]
    non_active_validators = [
        mock_validator_record(
            pubkey, deposit_size,
            default_end_dynasty,
            start_dynasty + 1
        )
        for pubkey in range(4)
    ]

    crystallized_state = empty_crystallized_state.copy(
        validators=active_validators + non_active_validators,
        current_dynasty=start_dynasty,
    )

    assert len(crystallized_state.active_validator_indices) == len(active_validators)

    expected_total_deposits = deposit_size * num_active_validators
    assert crystallized_state.total_deposits == expected_total_deposits


def test_hash(sample_crystallized_state_params):
    crystallized_state = CrystallizedState(**sample_crystallized_state_params)
    assert crystallized_state.hash == blake(rlp.encode(crystallized_state))
