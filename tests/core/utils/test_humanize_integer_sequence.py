import pytest

from trinity._utils.humanize import humanize_integer_sequence


@pytest.mark.parametrize(
    'seq,expected',
    (
        ((), '(empty)'),
        ((1,), '1'),
        ((2,), '2'),
        ((10,), '10'),
        ((1, 2, 3), '1-3'),
        (range(6), '0-5'),
        ((1, 2, 3, 7, 8, 9), '1-3|7-9'),
        ((1, 2, 3, 5, 7, 8, 9), '1-3|5|7-9'),
        ((1, 3, 4, 5, 7, 8, 9), '1|3-5|7-9'),
        ((1, 3, 4, 5, 9), '1|3-5|9'),
        # should accept a generator
        ((_ for _ in range(0)), '(empty)'),
        ((i for i in (1, 2, 3, 7, 8, 10)), '1-3|7-8|10'),
    ),
)
def test_humanize_integer_sequence(seq, expected):
    actual = humanize_integer_sequence(seq)
    assert actual == expected
