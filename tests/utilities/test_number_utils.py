from __future__ import unicode_literals

import pytest

from hypothesis import (
    given,
    strategies as st,
)

from evm.utils.number import (
    integer_to_big_endian,
    big_endian_to_integer,
    integer_to_32bytes,
    UINT_256_MAX,
)


integer_st = st.integers(min_value=0, max_value=UINT_256_MAX)


@given(value=integer_st)
def test_round_trip(value):
    value = big_endian_to_integer(integer_to_big_endian(value))


@given(value=integer_st)
def test_integer_to_32bytes_round_trip(value):
    value = big_endian_to_integer(integer_to_32bytes(value))
