import pytest

from eth.constants import UINT_256_MAX

from trinity.exceptions import OversizeObject
from trinity._utils.headers import sequence_builder


@pytest.mark.parametrize(
    'start_num, max_length, skip, reverse, expected',
    (
        (0, 0, 0, False, ()),
        (0, 0, 0, True, ()),
        (0, 0, 1, False, ()),
        (0, 0, 1, True, ()),
        (0, 1, 0, False, (0, )),
        (0, 1, 0, True, (0, )),
        (0, 1, 1, False, (0, )),
        (0, 1, 1, True, (0, )),
        (9, 1, 0, False, (9, )),
        (9, 1, 0, True, (9, )),
        (1, 3, 0, False, (1, 2, 3)),
        (0, 5, 1, False, (0, 2, 4, 6, 8)),
        (9, 5, 1, True, (9, 7, 5, 3, 1)),
        (1, 9, 0, True, (1, 0)),
        (UINT_256_MAX - 1, 4, 0, False, (UINT_256_MAX - 1, UINT_256_MAX, )),
        # can handle mildly large numbers
        (400000000, 1000000, 0, False, tuple(range(400000000, 401000000))),
    ),
)
def test_sequence(start_num, max_length, skip, reverse, expected):
    assert sequence_builder(start_num, max_length, skip, reverse) == expected


TOO_LONG = 2000000


@pytest.mark.parametrize('reverse', (True, False))
@pytest.mark.parametrize('start_num', (0, 400000000))
@pytest.mark.parametrize('skip', (0, 10000))
def test_oversize_sequence(start_num, skip, reverse):
    # Instead of using the specific constant, just use a rough TOO_LONG number
    # We don't need to worry about edge cases for this gut check
    with pytest.raises(OversizeObject):
        sequence_builder(start_num, TOO_LONG, skip, reverse)
