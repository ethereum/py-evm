import random

from hypothesis import given
from hypothesis import strategies as st
import pytest

from eth2._utils.bitfield import (
    get_bitfield_length,
    get_empty_bitfield,
    get_vote_count,
    has_voted,
    set_voted,
)


@pytest.mark.parametrize(
    "attester_count, bitfield_length",
    [(0, 0), (1, 1), (8, 1), (9, 2), (16, 2), (17, 3)],
)
def test_bitfield_length(attester_count, bitfield_length):
    assert get_bitfield_length(attester_count) == bitfield_length


def test_empty_bitfield():
    attesters = list(range(10))
    bitfield = get_empty_bitfield(len(attesters))

    for attester in attesters:
        assert not has_voted(bitfield, attester)


def test_bitfield_single_votes():
    attesters = list(range(10))
    bitfield = get_empty_bitfield(len(attesters))

    assert set_voted(bitfield, 0) == (
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    )
    assert set_voted(bitfield, 1) == (
        False,
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    )
    assert set_voted(bitfield, 2) == (
        False,
        False,
        True,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
    )
    assert set_voted(bitfield, 4) == (
        False,
        False,
        False,
        False,
        True,
        False,
        False,
        False,
        False,
        False,
    )
    assert set_voted(bitfield, 5) == (
        False,
        False,
        False,
        False,
        False,
        True,
        False,
        False,
        False,
        False,
    )
    assert set_voted(bitfield, 6) == (
        False,
        False,
        False,
        False,
        False,
        False,
        True,
        False,
        False,
        False,
    )
    assert set_voted(bitfield, 7) == (
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        True,
        False,
        False,
    )
    assert set_voted(bitfield, 8) == (
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        True,
        False,
    )
    assert set_voted(bitfield, 9) == (
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        False,
        True,
    )

    for voter in attesters:
        bitfield = set_voted((False,) * 16, voter)
        for attester in attesters:
            if attester == voter:
                assert has_voted(bitfield, attester)
            else:
                assert not has_voted(bitfield, attester)


def test_bitfield_all_votes():
    attesters = list(range(10))

    bitfield = get_empty_bitfield(len(attesters))
    for attester in attesters:
        bitfield = set_voted(bitfield, attester)

    for attester in attesters:
        assert has_voted(bitfield, attester)
    assert bitfield == (True,) * len(attesters)


def test_bitfield_some_votes():
    attesters = list(range(10))
    voters = [0, 4, 5, 9]  # b'\x01\x00'  # b'\x10\x00'  # b'\x20\x00'  # b'\x00\x02'

    bitfield = get_empty_bitfield(len(attesters))
    for voter in voters:
        bitfield = set_voted(bitfield, voter)

    assert bitfield == (
        True,
        False,
        False,
        False,
        True,
        True,
        False,
        False,
        False,
        True,
    )

    for attester in attesters:
        if attester in voters:
            assert has_voted(bitfield, attester)
        else:
            assert not has_voted(bitfield, attester)


def test_bitfield_multiple_votes():
    bitfield = get_empty_bitfield(1)
    bitfield = set_voted(bitfield, 0)
    bitfield = set_voted(bitfield, 0)
    assert has_voted(bitfield, 0)


def test_get_vote_count():
    bitfield = get_empty_bitfield(5)
    bitfield = set_voted(bitfield, 0)
    bitfield = set_voted(bitfield, 3)
    assert get_vote_count(bitfield) == 2


@given(st.integers(1, 1000))
def test_set_vote_and_has_vote(bit_count):
    bitfield = get_empty_bitfield(bit_count)
    index = random.choice(range(bit_count))
    bitfield = set_voted(bitfield, index)
    assert has_voted(bitfield, index)


@given(st.integers(1, 999))
def test_has_voted_random(votes_count):
    bit_count = 1000
    bitfield = get_empty_bitfield(bit_count)
    random_votes = random.sample(range(bit_count), votes_count)

    for index in random_votes:
        bitfield = set_voted(bitfield, index)
    assert get_vote_count(bitfield) == votes_count

    for index in range(bit_count):
        if index in random_votes:
            assert has_voted(bitfield, index)
        else:
            assert not has_voted(bitfield, index)
