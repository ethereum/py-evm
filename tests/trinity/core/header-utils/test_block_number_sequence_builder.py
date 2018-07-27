import pytest

from eth.constants import UINT_256_MAX
from trinity.utils.headers import sequence_builder


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
    ),
)
def test_sequence(start_num, max_length, skip, reverse, expected):
    assert sequence_builder(start_num, max_length, skip, reverse) == expected
