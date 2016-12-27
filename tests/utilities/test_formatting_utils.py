from __future__ import unicode_literals

import pytest

from hypothesis import (
    given,
    strategies as st,
)

from evm.utils.types import (
    is_text,
    is_bytes,
)
from evm.utils.string import (
    force_text,
)
from evm.utils.formatting import (
    pad_left,
    pad_right,
    is_prefixed,
    is_0x_prefixed,
    remove_0x_prefix,
    add_0x_prefix,
)


@pytest.mark.parametrize(
    "args,expected",
    (
        (('', 20), '00000000000000000000'),
        ((b'', 20), b'00000000000000000000'),
        (('abcd', 20), '0000000000000000abcd'),
        ((b'abcd', 20), b'0000000000000000abcd'),
        # Other char
        (('', 20, 'x'), 'xxxxxxxxxxxxxxxxxxxx'),
        (('', 20, b'x'), 'xxxxxxxxxxxxxxxxxxxx'),
        ((b'', 20, 'x'), b'xxxxxxxxxxxxxxxxxxxx'),
        ((b'', 20, b'x'), b'xxxxxxxxxxxxxxxxxxxx'),
        (('abcd', 20, 'x'), 'xxxxxxxxxxxxxxxxabcd'),
        (('abcd', 20, b'x'), 'xxxxxxxxxxxxxxxxabcd'),
        ((b'abcd', 20, 'x'), b'xxxxxxxxxxxxxxxxabcd'),
        ((b'abcd', 20, b'x'), b'xxxxxxxxxxxxxxxxabcd'),
    )
)
def test_pad_left(args, expected):
    actual = pad_left(*args)
    assert actual == expected


base_value_st = st.one_of(
    st.binary(min_size=0, max_size=64).map(force_text),
    st.binary(min_size=0, max_size=64),
)
length_st = st.integers(min_value=0, max_value=1024)
pad_char_st = st.one_of(
    st.binary(min_size=1, max_size=1).map(force_text).filter(lambda c: c != ''),
    st.binary(min_size=1, max_size=1).filter(lambda c: c != b''),
)

pad_args = st.one_of(
    st.tuples(base_value_st, length_st, pad_char_st),
    st.tuples(base_value_st, length_st),
)


@given(args=pad_args)
def test_fuzzy_pad_left(args):
    result = pad_left(*args)

    if len(args) == 3:
        value, length, pad_chr = args
    elif len(args) == 2:
        value, length = args
        pad_chr = '0'
    else:
        raise AssertionError("Invalid args length")

    if is_text(value):
        assert is_text(result)
    elif is_bytes(value):
        assert is_bytes(result)

    if len(value) <= length:
        assert len(result) == length
    else:
        assert result == value

    if len(value) < length:
        fill_amount = length - len(value)
        fill_value = force_text(result[:fill_amount])
        assert fill_value == force_text(pad_chr * fill_amount)


@pytest.mark.parametrize(
    "args,expected",
    (
        (('', 20), '00000000000000000000'),
        ((b'', 20), b'00000000000000000000'),
        (('abcd', 20), 'abcd0000000000000000'),
        ((b'abcd', 20), b'abcd0000000000000000'),
        # Other char
        (('', 20, 'x'), 'xxxxxxxxxxxxxxxxxxxx'),
        (('', 20, b'x'), 'xxxxxxxxxxxxxxxxxxxx'),
        ((b'', 20, 'x'), b'xxxxxxxxxxxxxxxxxxxx'),
        ((b'', 20, b'x'), b'xxxxxxxxxxxxxxxxxxxx'),
        (('abcd', 20, 'x'), 'abcdxxxxxxxxxxxxxxxx'),
        (('abcd', 20, b'x'), 'abcdxxxxxxxxxxxxxxxx'),
        ((b'abcd', 20, 'x'), b'abcdxxxxxxxxxxxxxxxx'),
        ((b'abcd', 20, b'x'), b'abcdxxxxxxxxxxxxxxxx'),
    )
)
def test_pad_right(args, expected):
    actual = pad_right(*args)
    assert actual == expected


@given(args=pad_args)
def test_fuzzy_pad_right(args):
    result = pad_right(*args)

    if len(args) == 3:
        value, length, pad_chr = args
    elif len(args) == 2:
        value, length = args
        pad_chr = '0'
    else:
        raise AssertionError("Invalid args length")

    if is_text(value):
        assert is_text(result)
    elif is_bytes(value):
        assert is_bytes(result)

    if len(value) <= length:
        assert len(result) == length
    else:
        assert result == value

    if len(value) < length:
        fill_amount = length - len(value)
        fill_value = force_text(result[-1 * fill_amount:])
        assert fill_value == force_text(pad_chr * fill_amount)


@pytest.mark.parametrize(
    'value,prefix,expected',
    (
        ('', '', True),
        ('abc', 'abc', True),
        (b'abc', 'abc', True),
        ('abc', b'abc', True),
        (b'abc', b'abc', True),
        # not correct prefix
        ('abc', 'abcd', False),
        (b'abc', 'abcd', False),
        ('abc', b'abcd', False),
        (b'abc', b'abcd', False),
        (' abc', 'abc', False),
        (b' abc', 'abc', False),
    )
)
def test_is_prefixed(value, prefix, expected):
    actual = is_prefixed(value, prefix)
    assert actual is expected


@pytest.mark.parametrize(
    'value,expected',
    (
        ('', False),
        ('abc', False),
        (b'abc', False),
        ('0x', True),
        (b'0x', True),
        ('0xabcd', True),
        (b'0xabcd', True),
        # not correct prefix
        (' 0xabcd', False),
        (b' 0xabcd', False),
    )
)
def test_is_0x_prefixed(value, expected):
    actual = is_0x_prefixed(value)
    assert actual is expected


@pytest.mark.parametrize(
    'value,expected',
    (
        ('', '0x'),
        (b'', b'0x'),
        ('0x', '0x'),
        (b'0x', b'0x'),
        ('abcd', '0xabcd'),
        (b'abcd', b'0xabcd'),
    )
)
def test_add_0x_prefix(value, expected):
    actual = add_0x_prefix(value)
    assert actual == expected


@pytest.mark.parametrize(
    'value,expected',
    (
        ('', ''),
        (b'', b''),
        ('0x', ''),
        (b'0x', b''),
        ('abcd', 'abcd'),
        (b'abcd', b'abcd'),
        ('0xabcd', 'abcd'),
        (b'0xabcd', b'abcd'),
    )
)
def test_remove_0x_prefix(value, expected):
    actual = remove_0x_prefix(value)
    assert actual == expected
