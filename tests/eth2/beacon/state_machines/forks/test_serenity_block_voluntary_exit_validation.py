
import pytest

from eth_utils import (
    ValidationError,
)

from eth2.beacon.constants import (
    FAR_FUTURE_EPOCH,
)
from eth2.beacon.helpers import (
    get_epoch_start_slot,
)
from eth2.beacon.state_machines.forks.serenity.block_validation import (
    validate_voluntary_exit,
    validate_voluntary_exit_epoch,
    validate_voluntary_exit_initiated_exit,
    validate_voluntary_exit_persistent,
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
        'persistent_committee_period',
    ),
    [
        (40, 2, 2, 16),
    ]
)
def test_validate_voluntary_exit(
        genesis_state,
        keymap,
        slots_per_epoch,
        persistent_committee_period,
        config):
    state = genesis_state.copy(
        slot=get_epoch_start_slot(
            config.GENESIS_EPOCH + persistent_committee_period,
            slots_per_epoch
        ),
    )
    validator_index = 0
    validator = state.validator_registry[validator_index].copy(
        activation_epoch=config.GENESIS_EPOCH,
    )
    state = state.update_validator_registry(validator_index, validator)
    valid_voluntary_exit = create_mock_voluntary_exit(
        state,
        config,
        keymap,
        validator_index,
    )
    validate_voluntary_exit(
        state,
        valid_voluntary_exit,
        slots_per_epoch,
        persistent_committee_period,
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
        'validator_exit_epoch',
        'success',
    ),
    [
        (FAR_FUTURE_EPOCH, True),
        (FAR_FUTURE_EPOCH - 1, False),
    ]
)
def test_validate_voluntary_validator_exit_epoch(
        genesis_state,
        validator_exit_epoch,
        success):
    state = genesis_state

    validator_index = 0

    validator = state.validator_registry[validator_index].copy(
        exit_epoch=validator_exit_epoch,
    )

    if success:
        validate_voluntary_exit_validator_exit_epoch(validator)
    else:
        with pytest.raises(ValidationError):
            validate_voluntary_exit_validator_exit_epoch(validator)


@pytest.mark.parametrize(
    (
        'initiated_exit',
        'success',
    ),
    [
        (False, True),
        (True, False),
    ]
)
def test_validate_voluntary_exit_initiated_exit(
        genesis_state,
        initiated_exit,
        success):
    state = genesis_state

    validator_index = 0

    validator = state.validator_registry[validator_index].copy(
        initiated_exit=initiated_exit,
    )

    if success:
        validate_voluntary_exit_initiated_exit(validator)
    else:
        with pytest.raises(ValidationError):
            validate_voluntary_exit_initiated_exit(validator)


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
        'current_epoch',
        'persistent_committee_period',
        'activation_epoch',
        'success',
    ),
    [
        (16, 4, 16 - 4, True),
        (16, 4, 16 - 4 + 1, False),
    ]
)
def test_validate_voluntary_exit_persistent(
        genesis_state,
        keymap,
        current_epoch,
        activation_epoch,
        slots_per_epoch,
        persistent_committee_period,
        success):
    state = genesis_state.copy(
        slot=get_epoch_start_slot(
            current_epoch,
            slots_per_epoch
        ),
    )
    validator_index = 0
    validator = state.validator_registry[validator_index].copy(
        activation_epoch=activation_epoch,
    )
    state = state.update_validator_registry(validator_index, validator)

    if success:
        validate_voluntary_exit_persistent(
            validator,
            state.current_epoch(slots_per_epoch),
            persistent_committee_period,
        )
    else:
        with pytest.raises(ValidationError):
            validate_voluntary_exit_persistent(
                validator,
                state.current_epoch(slots_per_epoch),
                persistent_committee_period,
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
