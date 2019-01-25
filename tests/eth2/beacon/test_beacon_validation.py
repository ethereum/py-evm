import pytest

from eth_utils import (
    ValidationError,
)

from eth2.beacon.validation import (
    validate_slot,
    validate_slot_for_state_slot,
)


@pytest.mark.parametrize(
    "slot,is_valid",
    (
        (tuple(), False),
        ([], False),
        ({}, False),
        (set(), False),
        ('abc', False),
        (1234, True),
        (-1, False),
        (0, True),
        (100, True),
        (2 ** 64, False),
    ),
)
def test_validate_slot(slot, is_valid):
    if is_valid:
        validate_slot(slot)
    else:
        with pytest.raises(ValidationError):
            validate_slot(slot)


@pytest.mark.parametrize(
    (
        'state_slot, slot, epoch_length, success'
    ),
    [
        (
            0, 0, 64, True,
        ),
        (
            64 * 2, 64, 64, True,
        ),
        (
            64 * 2, 64 - 1, 64, False,  # slot is too small
        ),
        (
            64 * 2, 64 * 3 - 1, 64, True,
        ),
        (
            64 * 2, 64 * 3, 64, False,  # slot is too large
        ),
    ]
)
def test_validate_slot_for_state_slot(state_slot, slot, epoch_length, success):
    if success:
        validate_slot_for_state_slot(
            state_slot=state_slot,
            slot=slot,
            epoch_length=epoch_length
        )
    else:
        with pytest.raises(ValidationError):
            validate_slot_for_state_slot(
                state_slot=state_slot,
                slot=slot,
                epoch_length=epoch_length
            )
