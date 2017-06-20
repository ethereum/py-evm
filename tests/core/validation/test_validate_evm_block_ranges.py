import pytest

from evm.exceptions import (
    ValidationError,
)
from evm.validation import (
    validate_vm_block_ranges,
)


@pytest.mark.parametrize(
    'ranges,should_error',
    (
        # open on both ends.
        (
            ((None, None),),
            False,
        ),
        # two ranges with open ends.
        (
            ((None, 10), (11, None)),
            False,
        ),
        # two ranges that intersect
        (
            ((None, 10), (10, None)),
            True,
        ),
        # two ranges with a gap
        (
            ((None, 10), (12, None)),
            True,
        ),
        # closed range across 3 sections
        (
            ((1, 10), (11, 20), (21, 30)),
            False,
        ),
        # closed range across 3 sections with open right end
        (
            ((1, 10), (11, 20), (21, None)),
            False,
        ),
        # closed range across 3 sections with open left end
        (
            ((None, 10), (11, 20), (21, 30)),
            False,
        ),
        # closed range across 3 sections open on both ends
        (
            ((None, 10), (11, 20), (21, None)),
            False,
        ),
        # range with gap across 3 sections
        (
            ((1, 10), (13, 20), (21, 30)),
            True,
        ),
        # range with overlap across 3 sections
        (
            ((1, 10), (11, 22), (21, 30)),
            True,
        ),
        # multiple open left bounds
        (
            ((None, 10), (11, 22), (None, 30)),
            True,
        ),
        # multiple open right bounds
        (
            ((1, 10), (11, None), (22, None)),
            True,
        ),
        # open bound in the middle
        (
            ((1, 10), (11, None), (22, 30)),
            True,
        ),
    ),
)
def test_validate_vm_block_ranges(ranges, should_error):
    if should_error:
        with pytest.raises(ValidationError):
            validate_vm_block_ranges(ranges)
    else:
        validate_vm_block_ranges(ranges)
