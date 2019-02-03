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
        'current_epoch, epoch, epoch_length, success'
    ),
    [
        (
            0, 0, 64, True,
        ),
        (
            64 * 2, 64, 64, True,
        ),
        (
            64 * 2, 64 - 1, 64, False,  # epoch is too small
        ),
        (
            64 * 2, 64 * 3 - 1, 64, True,
        ),
        (
            64 * 2, 64 * 3, 64, False,  # epoch is too large
        ),
    ]
)
def test_validate_epoch_for_current_epoch(
        current_epoch,
        epoch,
        epoch_length,
        success,
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
