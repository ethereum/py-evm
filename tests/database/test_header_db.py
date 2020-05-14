import operator
import random

import pytest

from eth_utils.toolz import accumulate

from eth_utils import (
    to_tuple,
    keccak,
    ValidationError,
)

from eth.constants import (
    GENESIS_BLOCK_NUMBER,
    GENESIS_DIFFICULTY,
    GENESIS_GAS_LIMIT,
)
from eth.db.chain_gaps import GapChange, GENESIS_CHAIN_GAPS
from eth.exceptions import (
    CanonicalHeadNotFound,
    HeaderNotFound,
    ParentNotFound,
)
from eth.db.header import HeaderDB
from eth.rlp.headers import (
    BlockHeader,
)
from eth.tools.rlp import (
    assert_headers_eq,
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

    headerdb.persist_header_chain(headers)

    head = headerdb.get_canonical_head()
    assert headerdb.get_score(head.hash) == 188978561024
    assert_headers_eq(head, headers[-1])


def test_headerdb_persist_disconnected_headers(headerdb, genesis_header):
    headerdb.persist_header(genesis_header)

    headers = mk_header_chain(genesis_header, length=10)

    score_at_pseudo_genesis = 154618822656
    # This is the score that we would reach at the tip if we persist the entire chain.
    # But we test to reach it by building on top of a trusted score.
    expected_score_at_tip = 188978561024

    pseudo_genesis = headers[7]

    assert headerdb.get_header_chain_gaps() == GENESIS_CHAIN_GAPS
    # Persist the checkpoint header with a trusted score
    headerdb.persist_checkpoint_header(pseudo_genesis, score_at_pseudo_genesis)
    assert headerdb.get_header_chain_gaps() == (((1, 7),), 9)

    assert_headers_eq(headerdb.get_canonical_head(), pseudo_genesis)

    headers_from_pseudo_genesis = (headers[8], headers[9],)

    headerdb.persist_header_chain(headers_from_pseudo_genesis, pseudo_genesis.parent_hash)
    assert headerdb.get_header_chain_gaps() == (((1, 7),), 11)
    head = headerdb.get_canonical_head()
    assert_headers_eq(head, headers[-1])
    assert headerdb.get_score(head.hash) == expected_score_at_tip

    header_8 = headerdb.get_block_header_by_hash(headers[8].hash)
    assert_headers_eq(header_8, headers[8])

    with pytest.raises(HeaderNotFound):
        headerdb.get_block_header_by_hash(headers[2].hash)


def test_can_patch_holes(headerdb, genesis_header):
    headerdb.persist_header(genesis_header)
    headers = mk_header_chain(genesis_header, length=10)

    assert headerdb.get_header_chain_gaps() == GENESIS_CHAIN_GAPS
    # Persist the checkpoint header with a trusted score
    # headers[7] has block number 8 because `headers` doesn't include the genesis
    pseudo_genesis = headers[7]
    headerdb.persist_checkpoint_header(pseudo_genesis, 154618822656)
    assert headerdb.get_header_chain_gaps() == (((1, 7),), 9)
    assert_headers_eq(headerdb.get_canonical_head(), pseudo_genesis)

    headerdb.persist_header_chain(headers[:7])
    assert headerdb.get_header_chain_gaps() == ((), 9)

    for number in range(1, 9):
        # Make sure we can lookup the headers by block number
        header_by_number = headerdb.get_canonical_block_header_by_number(number)
        assert header_by_number.block_number == headers[number - 1].block_number

    # Make sure patching the hole does not affect what our current head is
    assert_headers_eq(headerdb.get_canonical_head(), pseudo_genesis)


def test_write_batch_that_patches_gap_and_adds_new_at_the_tip(headerdb, genesis_header):
    headerdb.persist_header(genesis_header)
    headers = mk_header_chain(genesis_header, length=10)

    assert headerdb.get_header_chain_gaps() == GENESIS_CHAIN_GAPS
    # Persist the checkpoint header with a trusted score
    pseudo_genesis = headers[7]
    headerdb.persist_checkpoint_header(pseudo_genesis, 154618822656)
    assert headerdb.get_header_chain_gaps() == (((1, 7),), 9)
    assert_headers_eq(headerdb.get_canonical_head(), pseudo_genesis)

    headerdb.persist_header_chain(headers)
    assert headerdb.get_header_chain_gaps() == ((), 11)

    for number in range(1, len(headers)):
        # Make sure we can lookup the headers by block number
        header_by_number = headerdb.get_canonical_block_header_by_number(number)
        assert header_by_number.block_number == headers[number - 1].block_number
    # Make sure patching the hole does not affect what our current head is
    assert_headers_eq(headerdb.get_canonical_head(), headers[-1])


@pytest.mark.parametrize(
    'written_headers, evolving_gaps',
    (
        (   # consecutive updates, then overwriting existing header
            (1, 2, 1),
            (
                (GapChange.TailWrite, ((), 2)),
                (GapChange.TailWrite, ((), 3)),
                (GapChange.NoChange, ((), 3)),
            )
        ),
        (   # consecutive updates
            (1, 2, 3),
            (
                (GapChange.TailWrite, ((), 2)),
                (GapChange.TailWrite, ((), 3)),
                (GapChange.TailWrite, ((), 4)),
            )
        ),
        (   # missing a single header in the middle
            (1, 3),
            (
                (GapChange.TailWrite, ((), 2)),
                (GapChange.NewGap, (((2, 2),), 4)),
            )
        ),
        (   # missing three headers in the middle
            (1, 5),
            (
                (GapChange.TailWrite, ((), 2)),
                (GapChange.NewGap, (((2, 4),), 6)),
            )
        ),
        (   # missing three headers in the middle, then patching center, dividing existing hole
            (1, 5, 3),
            (
                (GapChange.TailWrite, ((), 2)),
                (GapChange.NewGap, (((2, 4),), 6)),
                (GapChange.GapSplit, (((2, 2), (4, 4),), 6,))
            )
        ),
        (   # multiple holes, shrinking them until they vanish
            (1, 10, 5, 2, 4, 3, 9, 8, 7, 6),
            (
                (GapChange.TailWrite, ((), 2)),
                (GapChange.NewGap, (((2, 9),), 11)),
                (GapChange.GapSplit, (((2, 4), (6, 9),), 11)),
                (GapChange.GapShrink, (((3, 4), (6, 9),), 11)),
                (GapChange.GapShrink, (((3, 3), (6, 9),), 11)),
                (GapChange.GapFill, (((6, 9),), 11)),
                (GapChange.GapShrink, (((6, 8),), 11)),
                (GapChange.GapShrink, (((6, 7),), 11)),
                (GapChange.GapShrink, (((6, 6),), 11)),
                (GapChange.GapFill, ((), 11)),
            )
        ),
    )
)
def test_gap_tracking(headerdb, genesis_header, written_headers, evolving_gaps):
    headerdb.persist_header(genesis_header)
    headers = mk_header_chain(genesis_header, length=15)

    current_info = GENESIS_CHAIN_GAPS

    for idx, block_number in enumerate(written_headers):
        # using block numbers for the test parameters keeps it easier to read
        block_idx = block_number - 1

        change, current_info = headerdb._update_header_chain_gaps(
            headerdb.db, headers[block_idx], current_info
        )

        assert current_info == evolving_gaps[idx][1]
        assert change == evolving_gaps[idx][0]


@pytest.mark.parametrize(
    'chain_length',
    (0, 1, 2, 3),
)
def test_headerdb_get_canonical_head_with_header_chain_iterator(
        headerdb,
        genesis_header,
        chain_length):

    headerdb.persist_header(genesis_header)
    headers = mk_header_chain(genesis_header, length=chain_length)

    headerdb.persist_header_chain(header for header in headers)

    head = headerdb.get_canonical_head()

    if chain_length == 0:
        assert_headers_eq(head, genesis_header)
    else:
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


def test_headerdb_persist_header_chain_disallows_non_contiguous_chain(headerdb, genesis_header):
    headerdb.persist_header(genesis_header)

    headers = mk_header_chain(genesis_header, length=3)

    non_contiguous_headers = (headers[0], headers[2], headers[1],)

    with pytest.raises(ValidationError, match="Non-contiguous chain"):
        headerdb.persist_header_chain(non_contiguous_headers)


def test_headerdb_persist_header_returns_new_canonical_chain(headerdb, genesis_header):
    gen_result, _ = headerdb.persist_header(genesis_header)
    assert gen_result == (genesis_header,)

    chain_a = mk_header_chain(genesis_header, 3)
    chain_b = mk_header_chain(genesis_header, 2)
    chain_c = mk_header_chain(genesis_header, 5)

    for header in chain_a:
        res, _ = headerdb.persist_header(header)
        assert res == (header,)

    for header in chain_b:
        res, _ = headerdb.persist_header(header)
        assert res == tuple()

    for idx, header in enumerate(chain_c, 1):
        res, _ = headerdb.persist_header(header)
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

    headerdb.persist_header_chain(headers)

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

    headerdb.persist_header_chain(headers)

    # can we get the genesis header by hash
    actual = headerdb.get_block_header_by_hash(genesis_header.hash)
    assert_headers_eq(actual, genesis_header)

    for header in headers:
        actual = headerdb.get_block_header_by_hash(header.hash)
        assert_headers_eq(actual, header)


def test_headerdb_canonical_header_retrieval_by_number(headerdb, genesis_header):
    headerdb.persist_header(genesis_header)

    headers = mk_header_chain(genesis_header, length=10)

    headerdb.persist_header_chain(headers)

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
