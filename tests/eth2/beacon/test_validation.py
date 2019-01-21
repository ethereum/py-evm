import pytest

from eth_utils import (
    ValidationError
)

from eth2.beacon.validation import (
    validate_slot_for_state_slot,
)


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
