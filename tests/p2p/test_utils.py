import pytest

from hypothesis import (
    given,
    strategies as st,
)

from p2p._utils import trim_middle


@pytest.mark.parametrize(
    "in_str, max_length, expected",
    (
        ("notcut", 6, "notcut"),
        ("tobecut", 6, "to✂✂✂t"),
        ("tobecut", 5, "t✂✂✂t"),
        ("0000", 3, "✂✂✂"),
        ("really long thing with a bunch of garbage", 20, "really lo✂✂✂ garbage"),
    )
)
def test_trim_middle(in_str, max_length, expected):
    actual = trim_middle(in_str, max_length)
    assert actual == expected


@given(st.text(), st.integers(min_value=3))
def test_trim_middle_length(in_str, max_length):
    result = trim_middle(in_str, max_length)

    # should never be longer than max length
    assert len(result) <= max_length

    if len(in_str) <= max_length:
        # should never be modified if the input is within max length
        assert in_str == result
    else:
        # should always have the trim marker if the input was too long
        assert "✂✂✂" in result
