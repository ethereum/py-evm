import random

from hypothesis import (
    given,
    strategies as st,
)
import pytest

from eth2._utils.bitfield import (
    has_voted,
    set_voted,
    get_bitfield_length,
    get_empty_bitfield,
    get_vote_count,
    or_bitfields,
)


@pytest.mark.parametrize(
    'attester_count, bitfield_length',
    [
        (0, 0),
        (1, 1),
        (8, 1),
        (9, 2),
        (16, 2),
        (17, 3),
    ]
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

    assert set_voted(bitfield, 0) == b'\x01\x00'
    assert set_voted(bitfield, 1) == b'\x02\x00'
    assert set_voted(bitfield, 2) == b'\x04\x00'
    assert set_voted(bitfield, 4) == b'\x10\x00'
    assert set_voted(bitfield, 5) == b'\x20\x00'
    assert set_voted(bitfield, 6) == b'\x40\x00'
    assert set_voted(bitfield, 7) == b'\x80\x00'
    assert set_voted(bitfield, 8) == b'\x00\x01'
    assert set_voted(bitfield, 9) == b'\x00\x02'

    for voter in attesters:
        bitfield = set_voted(b'\x00\x00', voter)
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
    assert bitfield == b'\xff\x03'


def test_bitfield_some_votes():
    attesters = list(range(10))
    voters = [
        0,  # b'\x01\x00'
        4,  # b'\x10\x00'
        5,  # b'\x20\x00'
        9,  # b'\x00\x02'
    ]

    bitfield = get_empty_bitfield(len(attesters))
    for voter in voters:
        bitfield = set_voted(bitfield, voter)

    assert bitfield == b'\x31\x02'

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


def test_or_bitfields():
    bitfield_1 = get_empty_bitfield(2)
    bitfield_1 = set_voted(bitfield_1, 0)
    assert get_vote_count(bitfield_1) == 1

    # same size as bitfield_1
    bitfield_2 = get_empty_bitfield(2)
    bitfield_2 = set_voted(bitfield_2, 1)
    assert get_vote_count(bitfield_2) == 1

    bitfield = or_bitfields([bitfield_1, bitfield_2])
    assert get_vote_count(bitfield) == 2

    # different size from bitfield_1
    bitfield_3 = get_empty_bitfield(100)
    bitfield_3 = set_voted(bitfield_3, 99)
    assert get_vote_count(bitfield_3) == 1

    with pytest.raises(ValueError):
        or_bitfields([bitfield_1, bitfield_3])


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


@given(
    st.lists(
        st.lists(elements=st.integers(0, 99), min_size=5, max_size=100, unique=True),
        min_size=1,
        max_size=100,
    )
)
def test_or_bitfields_random(votes):
    bitfields = []
    bit_count = 100

    for vote in votes:
        bitfield = get_empty_bitfield(bit_count)
        for index in vote:
            bitfield = set_voted(bitfield, index)
        bitfields.append(bitfield)

    bitfield = or_bitfields(bitfields)

    for index in range(bit_count):
        if has_voted(bitfield, index):
            assert any(has_voted(b, index) for b in bitfields)
