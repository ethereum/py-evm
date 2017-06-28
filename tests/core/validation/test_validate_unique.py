import pytest

from evm.exceptions import (
    ValidationError,
)
from evm.validation import (
    validate_unique,
)


@pytest.mark.parametrize(
    "value,is_valid",
    (
        (tuple(), True),
        ([], True),
        ({}, True),
        (set(), True),
        ([1, 2, 3], True),
        ([1, 2, 1], False),
        (['a', 'b', 'c'], True),
        (['1', '2', '3'], True),
        (['1', '2', '1'], False),
        (['1', '2', 1], True),
    ),
)
def test_validate_unique(value, is_valid):
    if is_valid:
        validate_unique(value)
    else:
        with pytest.raises(ValidationError):
            validate_unique(value)
