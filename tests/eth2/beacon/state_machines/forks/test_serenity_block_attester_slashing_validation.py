import pytest

from eth_utils import (
    ValidationError,
)

from eth2.beacon.helpers import (
    is_double_vote,
    is_surround_vote,
)
from eth2.beacon.state_machines.forks.serenity.block_validation import (
    validate_attester_slashing,
    validate_attester_slashing_different_data,
    validate_attester_slashing_slashing_conditions,
    validate_slashable_indices,
)
from eth2.beacon.tools.builder.validator import (
    create_mock_attester_slashing_is_double_vote,
    create_mock_attester_slashing_is_surround_vote,
    create_mock_slashable_attestation,
)


@pytest.mark.parametrize(
    (
        'num_validators',
        'slots_per_epoch',
        'target_committee_size',
        'shard_count',
    ),
    [
        (40, 2, 2, 2),
    ]
)
def test_validate_proposer_slashing_valid_double_vote(
        genesis_state,
        keymap,
        slots_per_epoch,
        max_indices_per_slashable_vote,
        config):
    attesting_state = genesis_state.copy(
        slot=genesis_state.slot + slots_per_epoch,
    )
    valid_attester_slashing = create_mock_attester_slashing_is_double_vote(
        attesting_state,
        config,
        keymap,
        attestation_epoch=0,
    )

    assert is_double_vote(
        valid_attester_slashing.slashable_attestation_1.data,
        valid_attester_slashing.slashable_attestation_2.data,
        slots_per_epoch,
    )
    assert not is_surround_vote(
        valid_attester_slashing.slashable_attestation_1.data,
        valid_attester_slashing.slashable_attestation_2.data,
        slots_per_epoch,
    )

    state = attesting_state.copy(
        slot=attesting_state.slot + 1,
    )
    validate_attester_slashing(
        state,
        valid_attester_slashing,
        max_indices_per_slashable_vote,
        slots_per_epoch,
    )


@pytest.mark.parametrize(
    (
        'num_validators',
        'slots_per_epoch',
        'target_committee_size',
        'shard_count',
    ),
    [
        (40, 2, 2, 2),
    ]
)
def test_validate_proposer_slashing_valid_is_surround_vote(
        genesis_state,
        keymap,
        slots_per_epoch,
        max_indices_per_slashable_vote,
        config):
    attesting_state = genesis_state.copy(
        slot=genesis_state.slot + slots_per_epoch,
    )
    valid_attester_slashing = create_mock_attester_slashing_is_surround_vote(
        attesting_state,
        config,
        keymap,
        attestation_epoch=attesting_state.current_epoch(slots_per_epoch),
    )

    assert not is_double_vote(
        valid_attester_slashing.slashable_attestation_1.data,
        valid_attester_slashing.slashable_attestation_2.data,
        slots_per_epoch,
    )
    assert is_surround_vote(
        valid_attester_slashing.slashable_attestation_1.data,
        valid_attester_slashing.slashable_attestation_2.data,
        slots_per_epoch,
    )

    state = attesting_state.copy(
        slot=attesting_state.slot + config.SLOTS_PER_EPOCH,
    )
    validate_attester_slashing(
        state,
        valid_attester_slashing,
        max_indices_per_slashable_vote,
        slots_per_epoch,
    )


@pytest.mark.parametrize(
    (
        'num_validators',
        'slots_per_epoch',
        'target_committee_size',
        'shard_count',
    ),
    [
        (40, 2, 2, 2),
    ]
)
def test_validate_attester_slashing_different_data(
        genesis_state,
        keymap,
        slots_per_epoch,
        config):
    attesting_state = genesis_state.copy(
        slot=genesis_state.slot + slots_per_epoch,
    )
    valid_attester_slashing = create_mock_attester_slashing_is_double_vote(
        attesting_state,
        config,
        keymap,
        attestation_epoch=0,
    )

    with pytest.raises(ValidationError):
        validate_attester_slashing_different_data(
            valid_attester_slashing.slashable_attestation_1,
            valid_attester_slashing.slashable_attestation_1,  # Put the same SlashableAttestation
        )


@pytest.mark.parametrize(
    (
        'num_validators',
        'slots_per_epoch',
        'target_committee_size',
        'shard_count',
    ),
    [
        (40, 2, 2, 2),
    ]
)
def test_validate_attester_slashing_slashing_conditions(
        genesis_state,
        keymap,
        slots_per_epoch,
        config):
    attesting_state_1 = genesis_state.copy(
        slot=genesis_state.slot + slots_per_epoch,
    )
    attesting_state_2 = attesting_state_1.copy(
        slot=attesting_state_1.slot + slots_per_epoch,
    )

    slashable_attestation_1 = create_mock_slashable_attestation(
        attesting_state_1,
        config,
        keymap,
        attestation_slot=attesting_state_1.slot + slots_per_epoch,
    )
    slashable_attestation_2 = create_mock_slashable_attestation(
        attesting_state_2,
        config,
        keymap,
        attestation_slot=attesting_state_2.slot + slots_per_epoch,
    )

    with pytest.raises(ValidationError):
        validate_attester_slashing_slashing_conditions(
            slashable_attestation_1,
            slashable_attestation_2,
            slots_per_epoch,
        )


@pytest.mark.parametrize(
    (
        'slashable_indices',
        'success',
    ),
    [
        ((), False),
        ((1,), True),
        ((1, 2), True),
    ]
)
def test_validate_slashable_indices(slashable_indices, success):
    if success:
        validate_slashable_indices(slashable_indices)
    else:
        with pytest.raises(ValidationError):
            validate_slashable_indices(slashable_indices)
