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


@given(st.integers(0, 2**256))
def test_is_power_of_two(value):
    expected = slow_is_power_of_two(value)
    assert expected == is_power_of_two(value)
