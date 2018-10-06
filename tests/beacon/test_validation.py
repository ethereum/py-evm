import pytest

from eth_utils import (
    ValidationError,
)

from eth.beacon.validation import (
    validate_slot,
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
