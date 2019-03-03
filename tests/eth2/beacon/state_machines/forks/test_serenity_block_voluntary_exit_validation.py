
import pytest

from eth_utils import (
    ValidationError,
)

from eth2.beacon.helpers import (
    get_epoch_start_slot,
)
from eth2.beacon.state_machines.forks.serenity.block_validation import (
    validate_voluntary_exit,
    validate_voluntary_exit_epoch,
    validate_voluntary_exit_signature,
    validate_voluntary_exit_validator_exit_epoch,
)
from eth2.beacon.tools.builder.validator import (
    create_mock_voluntary_exit,
)


@pytest.mark.parametrize(
    (
        'num_validators',
        'slots_per_epoch',
        'target_committee_size',
        'activation_exit_delay',
    ),
    [
        (40, 2, 2, 2),
    ]
)
def test_validate_voluntary_exit(
        genesis_state,
        keymap,
        slots_per_epoch,
        activation_exit_delay,
        config):
    state = genesis_state
    validator_index = 0
    valid_voluntary_exit = create_mock_voluntary_exit(
        state,
        config,
        keymap,
        validator_index,
    )
    validate_voluntary_exit(state, valid_voluntary_exit, slots_per_epoch, activation_exit_delay)


@pytest.mark.parametrize(
    (
        'num_validators',
        'genesis_slot',
        'genesis_epoch',
        'slots_per_epoch',
        'target_committee_size',
    ),
    [
        (40, 8, 4, 2, 2),
    ]
)
@pytest.mark.parametrize(
    (
        'activation_exit_delay',
        'current_epoch',
        'validator_exit_epoch',
        'success',
    ),
    [
        (4, 8, 4 + 8 + 1 + 1, True),
        (4, 8, 4 + 8 + 1, False),
    ]
)
def test_validate_voluntary_validator_exit_epoch(
        genesis_state,
        current_epoch,
        validator_exit_epoch,
        slots_per_epoch,
        activation_exit_delay,
        success):
    state = genesis_state.copy(
        slot=get_epoch_start_slot(current_epoch, slots_per_epoch),
    )

    validator_index = 0

    validator = state.validator_registry[validator_index].copy(
        exit_epoch=validator_exit_epoch,
    )

    if success:
        validate_voluntary_exit_validator_exit_epoch(
            state,
            validator,
            current_epoch,
            slots_per_epoch,
            activation_exit_delay,
        )
    else:
        with pytest.raises(ValidationError):
            validate_voluntary_exit_validator_exit_epoch(
                state,
                validator,
                current_epoch,
                slots_per_epoch,
                activation_exit_delay,
            )


@pytest.mark.parametrize(
    (
        'num_validators',
        'genesis_slot',
        'genesis_epoch',
        'slots_per_epoch',
        'target_committee_size',
    ),
    [
        (40, 8, 4, 2, 2),
    ]
)
@pytest.mark.parametrize(
    (
        'activation_exit_delay',
        'current_epoch',
        'voluntary_exit_epoch',
        'success',
    ),
    [
        (4, 8, 8, True),
        (4, 8, 8 + 1, False),
    ]
)
def test_validate_voluntary_exit_epoch(
        genesis_state,
        keymap,
        current_epoch,
        voluntary_exit_epoch,
        slots_per_epoch,
        config,
        success):
    state = genesis_state.copy(
        slot=get_epoch_start_slot(current_epoch, slots_per_epoch),
    )

    validator_index = 0
    voluntary_exit = create_mock_voluntary_exit(
        state,
        config,
        keymap,
        validator_index,
        exit_epoch=voluntary_exit_epoch,
    )
    if success:
        validate_voluntary_exit_epoch(voluntary_exit, state.current_epoch(slots_per_epoch))
    else:
        with pytest.raises(ValidationError):
            validate_voluntary_exit_epoch(voluntary_exit, state.current_epoch(slots_per_epoch))


@pytest.mark.parametrize(
    (
        'num_validators',
        'slots_per_epoch',
        'target_committee_size',
        'activation_exit_delay',
    ),
    [
        (40, 2, 2, 2),
    ]
)
@pytest.mark.parametrize(
    (
        'success',
    ),
    [
        (True,),
        (False,),
    ]
)
def test_validate_voluntary_exit_signature(
        genesis_state,
        keymap,
        config,
        success):
    state = genesis_state
    validator_index = 0
    voluntary_exit = create_mock_voluntary_exit(
        state,
        config,
        keymap,
        validator_index,
    )
    validator = state.validator_registry[validator_index]
    if success:
        validate_voluntary_exit_signature(state, voluntary_exit, validator)
    else:
        # Use wrong signature
        voluntary_exit = voluntary_exit.copy(
            signature=b'\x12' * 96,  # wrong signature
        )
        with pytest.raises(ValidationError):
            validate_voluntary_exit_signature(state, voluntary_exit, validator)
