import pytest

import rlp

from eth.beacon.types.active_state import (
    ActiveState,
)
from eth.beacon.types.attestation_record import (
    AttestationRecord,
)
from eth.utils.blake import (
    blake,
)


@pytest.mark.parametrize(
    'param,default_value',
    [
        ('pending_attestations', ()),
        ('recent_block_hashes', ()),
    ]
)
def test_defaults(param, default_value, sample_active_state_params):
    del sample_active_state_params[param]
    active_state = ActiveState(**sample_active_state_params)

    assert getattr(active_state, param) == default_value


@pytest.mark.parametrize(
    'expected', [(0), (1), (5)]
)
def test_num_pending_attestations(expected):
    attestations = [AttestationRecord() for i in range(expected)]
    active_state = ActiveState(
        pending_attestations=attestations,
    )

    assert active_state.num_pending_attestations == expected


@pytest.mark.parametrize(
    'expected', [(0), (1), (5)]
)
def test_num_recent_block_hashes(expected):
    recent_block_hashes = [blake(i.to_bytes(32, 'big')) for i in range(expected)]
    active_state = ActiveState(
        recent_block_hashes=recent_block_hashes,
    )

    assert active_state.num_recent_block_hashes == expected


def test_hash():
    active_state = ActiveState()
    assert active_state.hash == blake(rlp.encode(active_state))
