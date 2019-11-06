import random

import pytest

from eth_utils import to_tuple, keccak

from eth.constants import (
    GENESIS_BLOCK_NUMBER,
    GENESIS_DIFFICULTY,
    GENESIS_GAS_LIMIT,
)
from eth.db.header import HeaderDB
from eth.db.turbo import TurboDatabase, find_header_path
from eth.rlp.headers import (
    BlockHeader,
)


@pytest.fixture
def headerdb(base_db):
    return HeaderDB(base_db)


@pytest.fixture
def genesis_header():
    return BlockHeader(
        difficulty=GENESIS_DIFFICULTY,
        block_number=GENESIS_BLOCK_NUMBER,
        gas_limit=GENESIS_GAS_LIMIT,
    )


# copied from tests/database/test_header_db, maybe this belongs in some util package
def make_header(previous_header):
    return BlockHeader.from_parent(
        parent=previous_header,
        timestamp=previous_header.timestamp + 1,
        gas_limit=previous_header.gas_limit,
        difficulty=previous_header.difficulty,
        extra_data=keccak(random.randint(0, 1e18)),
    )


@to_tuple
def mk_header_chain(base_header, length):
    previous_header = base_header
    for _ in range(length):
        next_header = make_header(previous_header)
        yield next_header
        previous_header = next_header


def test_genesis_header_path(headerdb, genesis_header):
    headerdb.persist_header(genesis_header)

    reverse, forward = find_header_path(headerdb, genesis_header, genesis_header)
    assert reverse == ()
    assert forward == ()


def test_same_chain_single_header_path(headerdb, genesis_header):
    next_header = make_header(genesis_header)
    headerdb.persist_header_chain((genesis_header, next_header))

    reverse, forward = find_header_path(headerdb, genesis_header, next_header)
    assert reverse == ()
    assert forward == (next_header,)

    reverse, forward = find_header_path(headerdb, next_header, genesis_header)
    assert reverse == (next_header,)
    assert forward == ()


def test_small_fork(headerdb, genesis_header):
    left_header = make_header(genesis_header)
    right_header = make_header(genesis_header)

    for header in (genesis_header, left_header, right_header):
        headerdb.persist_header(header)

    reverse, forward = find_header_path(headerdb, left_header, right_header)
    assert reverse == (left_header,)
    assert forward == (right_header,)

    reverse, forward = find_header_path(headerdb, right_header, left_header)
    assert reverse == (right_header,)
    assert forward == (left_header,)


def test_fork_one_side_longer(headerdb, genesis_header):
    headerdb.persist_header(genesis_header)

    left_tip = genesis_header
    for _ in range(5):
        next_left = make_header(left_tip)
        headerdb.persist_header(next_left)
        left_tip = next_left

    right_tip = genesis_header
    for _ in range(10):
        next_right = make_header(right_tip)
        headerdb.persist_header(next_right)
        right_tip = next_right

    # TODO: Make this test more thorough by checking that every header matches. Some kind
    #       of property-based testing might be ideal!
    reverse, forward = find_header_path(headerdb, left_tip, right_tip)
    assert len(reverse) == 5
    assert len(forward) == 10

    assert reverse[0] == left_tip
    assert forward[-1] == right_tip

    reverse, forward = find_header_path(headerdb, right_tip, left_tip)
    assert len(reverse) == 10
    assert len(forward) == 5

    assert reverse[0] == right_tip
    assert forward[-1] == left_tip
