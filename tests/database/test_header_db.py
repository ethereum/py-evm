import operator
import random

import pytest

from cytoolz import accumulate

from eth_utils import (
    to_tuple,
    keccak,
)

from eth.constants import (
    GENESIS_BLOCK_NUMBER,
    GENESIS_DIFFICULTY,
    GENESIS_GAS_LIMIT,
)
from eth.exceptions import (
    CanonicalHeadNotFound,
    ParentNotFound,
)
from eth.db.backends.memory import MemoryDB
from eth.db.header import HeaderDB
from eth.rlp.headers import (
    BlockHeader,
)
from eth.utils.rlp import (
    ensure_rlp_objects_are_equal,
)


assert_headers_eq = ensure_rlp_objects_are_equal(obj_a_name='actual', obj_b_name='expected')


@pytest.fixture
def base_db():
    return MemoryDB()


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


@to_tuple
def mk_header_chain(base_header, length):
    previous_header = base_header
    for _ in range(length):
        next_header = BlockHeader.from_parent(
            parent=previous_header,
            timestamp=previous_header.timestamp + 1,
            gas_limit=previous_header.gas_limit,
            difficulty=previous_header.difficulty,
            extra_data=keccak(random.randint(0, 1e18)),
        )
        yield next_header
        previous_header = next_header


def test_headerdb_get_canonical_head_not_found(headerdb):
    with pytest.raises(CanonicalHeadNotFound):
        headerdb.get_canonical_head()


def test_headerdb_get_canonical_head_at_genesis(headerdb, genesis_header):
    headerdb.persist_header(genesis_header)

    head = headerdb.get_canonical_head()
    assert head == genesis_header


def test_headerdb_get_canonical_head_with_header_chain(headerdb, genesis_header):
    headerdb.persist_header(genesis_header)

    headers = mk_header_chain(genesis_header, length=10)

    for header in headers:
        headerdb.persist_header(header)

    head = headerdb.get_canonical_head()
    assert_headers_eq(head, headers[-1])


def test_headerdb_persist_header_disallows_unknown_parent(headerdb):
    header = BlockHeader(
        difficulty=GENESIS_DIFFICULTY,
        block_number=GENESIS_BLOCK_NUMBER,
        gas_limit=GENESIS_GAS_LIMIT,
        parent_hash=b'\x0f' * 32,
    )
    with pytest.raises(ParentNotFound, match="unknown parent"):
        headerdb.persist_header(header)


def test_headerdb_persist_header_returns_new_canonical_chain(headerdb, genesis_header):
    gen_result = headerdb.persist_header(genesis_header)
    assert gen_result == (genesis_header,)

    chain_a = mk_header_chain(genesis_header, 3)
    chain_b = mk_header_chain(genesis_header, 2)
    chain_c = mk_header_chain(genesis_header, 5)

    for header in chain_a:
        res = headerdb.persist_header(header)
        assert res == (header,)

    for header in chain_b:
        res = headerdb.persist_header(header)
        assert res == tuple()

    for idx, header in enumerate(chain_c, 1):
        res = headerdb.persist_header(header)
        if idx <= 3:
            # prior to passing up `chain_a` each import should not return new
            # canonical headers.
            assert res == tuple()
        elif idx == 4:
            # at the point where `chain_c` passes `chain_a` we should get the
            # headers from `chain_c` up through current.
            assert res == chain_c[:idx]
            assert_headers_eq(res[-1], header)
        else:
            # after `chain_c` has become canonical we should just get each new
            # header back.
            assert res == (header,)


def test_headerdb_get_score_for_genesis_header(headerdb, genesis_header):
    headerdb.persist_header(genesis_header)
    score = headerdb.get_score(genesis_header.hash)
    assert score == genesis_header.difficulty


def test_headerdb_get_score_for_non_genesis_headers(headerdb, genesis_header):
    headerdb.persist_header(genesis_header)

    headers = mk_header_chain(genesis_header, length=10)
    difficulties = tuple(h.difficulty for h in headers)
    scores = tuple(accumulate(operator.add, difficulties, genesis_header.difficulty))

    for header in headers:
        headerdb.persist_header(header)

    for header, expected_score in zip(headers, scores[1:]):
        actual_score = headerdb.get_score(header.hash)
        assert actual_score == expected_score


def assert_is_canonical_chain(headerdb, headers):
    if not headers:
        return

    # verify that the HEAD is correctly set.
    head = headerdb.get_canonical_head()
    assert_headers_eq(head, headers[-1])

    # verify that each header is set as the canonical block.
    for header in headers:
        canonical_hash = headerdb.get_canonical_block_hash(header.block_number)
        assert canonical_hash == header.hash

    # verify difficulties are correctly set.
    base_header = headerdb.get_block_header_by_hash(headers[0].parent_hash)

    difficulties = tuple(h.difficulty for h in headers)
    scores = tuple(accumulate(operator.add, difficulties, base_header.difficulty))

    for header, expected_score in zip(headers, scores[1:]):
        actual_score = headerdb.get_score(header.hash)
        assert actual_score == expected_score


def test_headerdb_canonical_head_updates_to_longest_chain(headerdb, genesis_header):
    headerdb.persist_header(genesis_header)

    chain_a = mk_header_chain(genesis_header, 7)
    chain_b = mk_header_chain(genesis_header, 5)
    chain_c = mk_header_chain(genesis_header, 9)

    # insert `chain_a` into the database and verify that each block becomes the canonical head.
    for idx, header in enumerate(chain_a, 1):
        headerdb.persist_header(header)
        assert_is_canonical_chain(headerdb, chain_a[:idx])

    # insert `chain_b` into the database, verify that it does not become canonical.
    for header in chain_b:
        headerdb.persist_header(header)
        # chain should remain on `chain_a`
        assert_is_canonical_chain(headerdb, chain_a)

    # insert `chain_c` which should overtake `chain_a` as the cononical chain.
    for idx, header in enumerate(chain_c, 1):
        headerdb.persist_header(header)

        # HEAD should remain at the tip of `chain_a` until *after* the 8th header is imported
        if idx <= 7:
            assert_is_canonical_chain(headerdb, chain_a)
        else:
            assert_is_canonical_chain(headerdb, chain_c[:idx])

    assert_is_canonical_chain(headerdb, chain_c)


def test_headerdb_header_retrieval_by_hash(headerdb, genesis_header):
    headerdb.persist_header(genesis_header)

    headers = mk_header_chain(genesis_header, length=10)

    for header in headers:
        headerdb.persist_header(header)

    # can we get the genesis header by hash
    actual = headerdb.get_block_header_by_hash(genesis_header.hash)
    assert_headers_eq(actual, genesis_header)

    for header in headers:
        actual = headerdb.get_block_header_by_hash(header.hash)
        assert_headers_eq(actual, header)


def test_headerdb_canonical_header_retrieval_by_number(headerdb, genesis_header):
    headerdb.persist_header(genesis_header)

    headers = mk_header_chain(genesis_header, length=10)

    for header in headers:
        headerdb.persist_header(header)

    # can we get the genesis header by hash
    actual = headerdb.get_canonical_block_header_by_number(genesis_header.block_number)
    assert_headers_eq(actual, genesis_header)

    for header in headers:
        actual = headerdb.get_canonical_block_header_by_number(header.block_number)
        assert_headers_eq(actual, header)


def test_headerdb_header_exists(headerdb, genesis_header):
    assert headerdb.header_exists(genesis_header.hash) is False
    headerdb.persist_header(genesis_header)
    assert headerdb.header_exists(genesis_header.hash) is True

    chain_a = mk_header_chain(genesis_header, 3)
    chain_b = mk_header_chain(genesis_header, 5)

    assert not any(headerdb.header_exists(h.hash) for h in chain_a)
    assert not any(headerdb.header_exists(h.hash) for h in chain_b)

    for idx, header in enumerate(chain_a):
        assert all(headerdb.header_exists(h.hash) for h in chain_a[:idx])
        assert not any(headerdb.header_exists(h.hash) for h in chain_a[idx:])

        # sanity pre-check
        assert not headerdb.header_exists(header.hash)
        headerdb.persist_header(header)
        assert headerdb.header_exists(header.hash)

    # `chain_a` should now all exist
    assert all(headerdb.header_exists(h.hash) for h in chain_a)
    # `chain_b` should not be in the database.
    assert not any(headerdb.header_exists(h.hash) for h in chain_b)

    for idx, header in enumerate(chain_b):
        # `chain_a` should remain accessible
        assert all(headerdb.header_exists(h.hash) for h in chain_a)

        assert all(headerdb.header_exists(h.hash) for h in chain_b[:idx])
        assert not any(headerdb.header_exists(h.hash) for h in chain_b[idx:])

        # sanity pre-check
        assert not headerdb.header_exists(header.hash)
        headerdb.persist_header(header)
        assert headerdb.header_exists(header.hash)

    # both `chain_a` & `chain_b` should now all exist
    assert all(headerdb.header_exists(h.hash) for h in chain_a)
    assert all(headerdb.header_exists(h.hash) for h in chain_b)
