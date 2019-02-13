import math

from hypothesis import (
    given,
    strategies as st,
)

from eth2._utils.numeric import (
    is_power_of_two,
)


def slow_is_power_of_two(value):
    num = 2

    if value == 0:
        return False
    elif value == 1:
        return True

    while num < value:
        num *= 2

    return num == value


def fast_is_power_of_two(value: int) -> bool:
    """
    Check if ``value`` is a power of two integer.
    """
    if value == 0:
        return False
    else:
        return 2**int(math.log2(value)) == value


@given(st.integers(0, 2**256))
def test_is_power_of_two(value):
    slow_expected = slow_is_power_of_two(value)
    fast_expected = fast_is_power_of_two(value)
    assert slow_expected == fast_expected
    assert fast_expected == is_power_of_two(value)
