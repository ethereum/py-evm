import pytest

from eth_utils import (
    ValidationError,
)

from eth2.beacon.validation import (
    validate_slot,
    validate_epoch_for_current_epoch,
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
        'current_epoch, epoch, success'
    ),
    [
        (
            0, 0, True,
        ),
        (
            1, 0, True,
        ),
        (
            2, 0, False,  # epoch < previous_epoch
        ),
        (
            2, 2, True,
        ),
        (
            2, 3, False,  # next_epoch == epoch
        ),
    ]
)
def test_validate_epoch_for_current_epoch(
        current_epoch,
        epoch,
        success,
        epoch_length,
        genesis_epoch):
    if success:
        validate_epoch_for_current_epoch(
            current_epoch=current_epoch,
            given_epoch=epoch,
            genesis_epoch=genesis_epoch,
            epoch_length=epoch_length
        )
    else:
        with pytest.raises(ValidationError):
            validate_epoch_for_current_epoch(
                current_epoch=current_epoch,
                given_epoch=epoch,
                genesis_epoch=genesis_epoch,
                epoch_length=epoch_length
            )
