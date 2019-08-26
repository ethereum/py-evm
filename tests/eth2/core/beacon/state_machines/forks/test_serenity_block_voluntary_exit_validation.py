from eth_utils import ValidationError
import pytest

from eth2.beacon.constants import FAR_FUTURE_EPOCH
from eth2.beacon.helpers import compute_start_slot_of_epoch
from eth2.beacon.state_machines.forks.serenity.block_validation import (
    _validate_eligible_exit_epoch,
    _validate_validator_has_not_exited,
    _validate_validator_minimum_lifespan,
    _validate_voluntary_exit_signature,
    validate_voluntary_exit,
)
from eth2.beacon.tools.builder.validator import create_mock_voluntary_exit


@pytest.mark.parametrize(
    (
        "validator_count",
        "slots_per_epoch",
        "target_committee_size",
        "persistent_committee_period",
    ),
    [(40, 2, 2, 16)],
)
def test_validate_voluntary_exit(
    genesis_state, keymap, slots_per_epoch, persistent_committee_period, config
):
    state = genesis_state.copy(
        slot=compute_start_slot_of_epoch(
            config.GENESIS_EPOCH + persistent_committee_period, slots_per_epoch
        )
    )
    validator_index = 0
    valid_voluntary_exit = create_mock_voluntary_exit(
        state, config, keymap, validator_index
    )
    validate_voluntary_exit(
        state, valid_voluntary_exit, slots_per_epoch, persistent_committee_period
    )


@pytest.mark.parametrize(
    ("validator_count", "slots_per_epoch", "target_committee_size"), [(40, 2, 2)]
)
@pytest.mark.parametrize(
    ("validator_exit_epoch", "success"),
    [(FAR_FUTURE_EPOCH, True), (FAR_FUTURE_EPOCH - 1, False)],
)
def test_validate_validator_has_not_exited(
    genesis_state, validator_exit_epoch, success
):
    state = genesis_state

    validator_index = 0

    validator = state.validators[validator_index].copy(exit_epoch=validator_exit_epoch)

    if success:
        _validate_validator_has_not_exited(validator)
    else:
        with pytest.raises(ValidationError):
            _validate_validator_has_not_exited(validator)


@pytest.mark.parametrize(
    ("validator_count", "slots_per_epoch", "target_committee_size"), [(40, 2, 2)]
)
@pytest.mark.parametrize(
    ("activation_exit_delay", "current_epoch", "voluntary_exit_epoch", "success"),
    [(4, 8, 8, True), (4, 8, 8 + 1, False)],
)
def test_validate_eligible_exit_epoch(
    genesis_state,
    keymap,
    current_epoch,
    voluntary_exit_epoch,
    slots_per_epoch,
    config,
    success,
):
    state = genesis_state.copy(
        slot=compute_start_slot_of_epoch(current_epoch, slots_per_epoch)
    )

    validator_index = 0
    voluntary_exit = create_mock_voluntary_exit(
        state, config, keymap, validator_index, exit_epoch=voluntary_exit_epoch
    )
    if success:
        _validate_eligible_exit_epoch(
            voluntary_exit.epoch, state.current_epoch(slots_per_epoch)
        )
    else:
        with pytest.raises(ValidationError):
            _validate_eligible_exit_epoch(
                voluntary_exit.epoch, state.current_epoch(slots_per_epoch)
            )


@pytest.mark.parametrize(
    ("current_epoch", "persistent_committee_period", "activation_epoch", "success"),
    [(16, 4, 16 - 4, True), (16, 4, 16 - 4 + 1, False)],
)
def test_validate_validator_minimum_lifespan(
    genesis_state,
    keymap,
    current_epoch,
    activation_epoch,
    slots_per_epoch,
    persistent_committee_period,
    success,
):
    state = genesis_state.copy(
        slot=compute_start_slot_of_epoch(current_epoch, slots_per_epoch)
    )
    validator_index = 0
    validator = state.validators[validator_index].copy(
        activation_epoch=activation_epoch
    )
    state = state.update_validator(validator_index, validator)

    if success:
        _validate_validator_minimum_lifespan(
            validator, state.current_epoch(slots_per_epoch), persistent_committee_period
        )
    else:
        with pytest.raises(ValidationError):
            _validate_validator_minimum_lifespan(
                validator,
                state.current_epoch(slots_per_epoch),
                persistent_committee_period,
            )


@pytest.mark.parametrize(
    (
        "validator_count",
        "slots_per_epoch",
        "target_committee_size",
        "activation_exit_delay",
    ),
    [(40, 2, 2, 2)],
)
@pytest.mark.parametrize(("success",), [(True,), (False,)])
def test_validate_voluntary_exit_signature(genesis_state, keymap, config, success):
    slots_per_epoch = config.SLOTS_PER_EPOCH
    state = genesis_state
    validator_index = 0
    voluntary_exit = create_mock_voluntary_exit(state, config, keymap, validator_index)
    validator = state.validators[validator_index]
    if success:
        _validate_voluntary_exit_signature(
            state, voluntary_exit, validator, slots_per_epoch
        )
    else:
        # Use wrong signature
        voluntary_exit = voluntary_exit.copy(signature=b"\x12" * 96)  # wrong signature
        with pytest.raises(ValidationError):
            _validate_voluntary_exit_signature(
                state, voluntary_exit, validator, slots_per_epoch
            )
