import pytest

import rlp

from eth.constants import (
    ZERO_HASH32,
)
from eth.beacon.types.crystallized_state import (
    CrystallizedState,
)
from eth.beacon.types.crosslink_record import (
    CrosslinkRecord,
)
from eth.utils.blake import (
    blake,
)

from tests.beacon.helpers import (
    mock_validator_record,
)


@pytest.mark.parametrize(
    'param,default_value',
    [
        ('validators', ()),
        ('last_state_recalc', 0),
        ('shard_and_committee_for_slots', ()),
        ('last_justified_slot', 0),
        ('justified_streak', 0),
        ('last_finalized_slot', 0),
        ('current_dynasty', 0),
        ('crosslink_records', ()),
        ('dynasty_seed', ZERO_HASH32),
        ('dynasty_start', 0),
    ]
)
def test_defaults(param, default_value, sample_crystallized_state_params):
    del sample_crystallized_state_params[param]
    crystallized_state = CrystallizedState(**sample_crystallized_state_params)

    assert getattr(crystallized_state, param) == default_value


@pytest.mark.parametrize(
    'expected', [(0), (1), (5)]
)
def test_num_validators(expected):
    validators = [mock_validator_record(pubkey) for pubkey in range(expected)]
    crystallized_state = CrystallizedState(
        validators=validators,
    )

    assert crystallized_state.num_validators == expected


@pytest.mark.parametrize(
    'expected', [(0), (1), (5)]
)
def test_num_crosslink_records(expected):
    crosslink_records = [
        CrosslinkRecord() for i in range(expected)
    ]
    crystallized_state = CrystallizedState(
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
def test_total_deposits(num_active_validators, config):
    start_dynasty = 10
    active_validators = [
        mock_validator_record(pubkey, start_dynasty=start_dynasty)
        for pubkey in range(num_active_validators)
    ]
    non_active_validators = [
        mock_validator_record(pubkey, start_dynasty=start_dynasty + 1)
        for pubkey in range(4)
    ]
    crystallized_state = CrystallizedState(
        validators=active_validators + non_active_validators,
        current_dynasty=start_dynasty
    )

    assert len(crystallized_state.active_validator_indices) == len(active_validators)

    expected_total_deposits = config['deposit_size'] * num_active_validators
    assert crystallized_state.total_deposits == expected_total_deposits


def test_hash():
    crystallized_state = CrystallizedState()
    assert crystallized_state.hash == blake(rlp.encode(crystallized_state))
