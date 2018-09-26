import pytest

from eth.utils.bitfield import (
    has_voted,
    set_voted,
    get_bitfield_length,
    get_empty_bitfield,
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

    assert set_voted(bitfield, 0) == b'\x80\x00'
    assert set_voted(bitfield, 1) == b'\x40\x00'
    assert set_voted(bitfield, 2) == b'\x20\x00'
    assert set_voted(bitfield, 7) == b'\x01\x00'
    assert set_voted(bitfield, 8) == b'\x00\x80'
    assert set_voted(bitfield, 9) == b'\x00\x40'

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
    assert bitfield == b'\xff\xc0'


def test_bitfield_some_votes():
    attesters = list(range(10))
    voters = [0, 4, 5, 9]

    bitfield = get_empty_bitfield(len(attesters))
    for voter in voters:
        bitfield = set_voted(bitfield, voter)

    assert bitfield == b'\x8c\x40'

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
