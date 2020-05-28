import enum
from functools import partial
import operator
import random

from hypothesis import (
    example,
    given,
    strategies as st,
)
import pytest

from eth_utils.toolz import (
    accumulate,
    compose,
    sliding_window,
)

from eth_utils import (
    to_set,
    to_tuple,
    keccak,
    ValidationError,
)

from eth.constants import (
    GENESIS_BLOCK_NUMBER,
    GENESIS_DIFFICULTY,
    GENESIS_GAS_LIMIT,
)
from eth.db.chain_gaps import (
    GapChange,
    GENESIS_CHAIN_GAPS,
    fill_gap,
    reopen_gap,
    is_block_number_in_gap,
)
from eth.exceptions import (
    CanonicalHeadNotFound,
    GapTrackingCorrupted,
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


@pytest.fixture(scope="module")
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


def get_score(genesis_header, children):
    return sum(header.difficulty for header in children) + genesis_header.difficulty


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

    # This is the score that we would reach at the tip if we persist the entire chain.
    # But we test to reach it by building on top of a trusted score.
    expected_score_at_tip = get_score(genesis_header, headers)

    pseudo_genesis = headers[7]
    pseudo_genesis_score = get_score(genesis_header, headers[0:8])

    assert headerdb.get_header_chain_gaps() == GENESIS_CHAIN_GAPS
    # Persist the checkpoint header with a trusted score
    headerdb.persist_checkpoint_header(pseudo_genesis, pseudo_genesis_score)
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


def test_corrupt_gaps():
    with pytest.raises(GapTrackingCorrupted, match="(1, 3)"):
        fill_gap(2, (((1, 3), (2, 4)), 6))
    with pytest.raises(GapTrackingCorrupted, match="(2, 4)"):
        fill_gap(2, (((1, 3), (2, 4)), 6))


class StepAction(enum.Enum):
    PERSIST_CHECKPOINT = enum.auto()
    PERSIST_HEADERS = enum.auto()
    VERIFY_GAPS = enum.auto()
    VERIFY_CANONICAL_HEAD = enum.auto()
    VERIFY_CANONICAL_HEADERS = enum.auto()
    VERIFY_PERSIST_RAISES = enum.auto()


def _all_gap_numbers(chain_gaps, highest_block_number):
    """List all the missing headers, the block numbers in gaps"""
    gap_ranges, tail = chain_gaps
    for low, high in gap_ranges:
        yield from range(low, high + 1)
    yield from range(tail, highest_block_number + 1)


def _validate_gap_invariants(gaps):
    # 1. gaps are sorted
    for low, high in gaps[0]:
        assert high >= low, gaps

    # 2. gaps are not overrlapping
    for low_range, high_range in sliding_window(2, gaps[0]):
        # the top of the low range must not be sequential with the bottom of the high range
        assert low_range[1] + 1 < high_range[0], gaps

    # 3. final gap does not overlap with the tail
    if len(gaps[0]):
        final_gap_range = gaps[0][-1]
        assert final_gap_range[1] + 1 < gaps[1], gaps


@pytest.mark.parametrize(
    'steps',
    (
        # Start patching gap with uncles, later overwrite with true chain
        (
            (StepAction.PERSIST_CHECKPOINT, 8),
            (StepAction.VERIFY_GAPS, (((1, 7),), 9)),
            (StepAction.VERIFY_CANONICAL_HEAD, 8),
            (StepAction.PERSIST_HEADERS, ('b', lambda headers: headers[:3])),
            (StepAction.VERIFY_GAPS, (((4, 7),), 9)),
            (StepAction.VERIFY_CANONICAL_HEADERS, ('b', lambda headers: headers[:3])),
            # Verify patching the gap does not affect what our current head is
            (StepAction.VERIFY_CANONICAL_HEAD, 8),
            (StepAction.PERSIST_HEADERS, ('a', lambda headers: headers)),
            # It's important to verify all headers of a became canonical because there was a point
            # in time where the chain "thought" we already had filled 1 - 3 but they later turned
            # out to be uncles.
            (StepAction.VERIFY_CANONICAL_HEADERS, ('a', lambda headers: headers)),
            (StepAction.VERIFY_GAPS, ((), 11)),
        ),
        # Can not close gap with uncle chain
        (
            (StepAction.PERSIST_CHECKPOINT, 8),
            (StepAction.VERIFY_GAPS, (((1, 7),), 9)),
            (StepAction.VERIFY_CANONICAL_HEAD, 8),
            (StepAction.VERIFY_PERSIST_RAISES, ('b', ValidationError, lambda h: h[:7])),
            (StepAction.VERIFY_GAPS, (((1, 7),), 9)),
        ),
        # Can not fill gaps non-sequentially (backwards from checkpoint)
        (
            (StepAction.PERSIST_CHECKPOINT, 4),
            (StepAction.VERIFY_GAPS, (((1, 3),), 5)),
            (StepAction.VERIFY_CANONICAL_HEAD, 4),
            (StepAction.VERIFY_PERSIST_RAISES, ('b', ParentNotFound, lambda headers: [headers[2]])),
            (StepAction.VERIFY_PERSIST_RAISES, ('a', ParentNotFound, lambda headers: [headers[2]])),
            (StepAction.VERIFY_GAPS, (((1, 3),), 5)),
        ),
        # Can close gap, when head has advanced from checkpoint header
        (
            (StepAction.PERSIST_CHECKPOINT, 4),
            (StepAction.PERSIST_HEADERS, ('a', lambda headers: [headers[4]])),
            (StepAction.VERIFY_GAPS, (((1, 3),), 6)),
            (StepAction.VERIFY_CANONICAL_HEAD, 5),
            (StepAction.PERSIST_HEADERS, ('a', lambda headers: headers[:3])),
            (StepAction.VERIFY_GAPS, ((), 6)),
        ),
        # Can close gap that ends at checkpoint header
        (
            (StepAction.PERSIST_CHECKPOINT, 4),
            (StepAction.VERIFY_GAPS, (((1, 3),), 5)),
            (StepAction.VERIFY_CANONICAL_HEAD, 4),
            (StepAction.PERSIST_HEADERS, ('a', lambda headers: headers[:3])),
            (StepAction.VERIFY_GAPS, ((), 5)),
        ),
        # Open new gaps, while filling in previous gaps
        (
            (StepAction.PERSIST_CHECKPOINT, 4),
            (StepAction.VERIFY_GAPS, (((1, 3),), 5)),
            (StepAction.VERIFY_CANONICAL_HEAD, 4),
            (StepAction.PERSIST_HEADERS, ('a', lambda headers: headers[:2])),
            (StepAction.VERIFY_GAPS, (((3, 3),), 5)),
            # Create another gap
            (StepAction.PERSIST_CHECKPOINT, 8),
            (StepAction.VERIFY_CANONICAL_HEAD, 8),
            (StepAction.VERIFY_GAPS, (((3, 3), (5, 7),), 9)),
            # Work on the second gap but don't close
            (StepAction.PERSIST_HEADERS, ('a', lambda headers: headers[4:6])),
            (StepAction.VERIFY_GAPS, (((3, 3), (7, 7)), 9)),
            # Close first gap
            (StepAction.PERSIST_HEADERS, ('a', lambda headers: [headers[2]])),
            (StepAction.VERIFY_GAPS, (((7, 7),), 9)),
            # Close second gap
            (StepAction.PERSIST_HEADERS, ('a', lambda headers: [headers[6]])),
            (StepAction.VERIFY_GAPS, ((), 9)),
        ),
    ),
)
def test_different_cases_of_patching_gaps(headerdb, genesis_header, steps):
    headerdb.persist_header(genesis_header)
    chain_a = mk_header_chain(genesis_header, length=10)
    chain_b = mk_header_chain(genesis_header, length=10)

    def _get_chain(id):
        if chain_id == 'a':
            return chain_a
        elif chain_id == 'b':
            return chain_b
        else:
            raise Exception(f"Invalid chain id: {chain_id}")

    assert headerdb.get_header_chain_gaps() == GENESIS_CHAIN_GAPS

    for step in steps:
        step_action, step_data = step
        if step_action is StepAction.PERSIST_CHECKPOINT:
            pseudo_genesis = chain_a[step_data - 1]
            pseudo_genesis_score = get_score(genesis_header, chain_a[0:step_data])
            headerdb.persist_checkpoint_header(pseudo_genesis, pseudo_genesis_score)
        elif step_action is StepAction.PERSIST_HEADERS:
            chain_id, selector_fn = step_data
            headerdb.persist_header_chain(selector_fn(_get_chain(chain_id)))
        elif step_action is StepAction.VERIFY_GAPS:
            assert headerdb.get_header_chain_gaps() == step_data
        elif step_action is StepAction.VERIFY_PERSIST_RAISES:
            chain_id, error, selector_fn = step_data
            with pytest.raises(error):
                headerdb.persist_header_chain(selector_fn(_get_chain(chain_id)))
        elif step_action is StepAction.VERIFY_CANONICAL_HEAD:
            assert_headers_eq(headerdb.get_canonical_head(), chain_a[step_data - 1])
        elif step_action is StepAction.VERIFY_CANONICAL_HEADERS:
            chain_id, selector_fn = step_data
            for header in selector_fn(_get_chain(chain_id)):
                assert headerdb.get_canonical_block_header_by_number(header.block_number) == header
        else:
            raise Exception("Unknown step action")


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
                (GapChange.GapLeftShrink, (((3, 4), (6, 9),), 11)),
                (GapChange.GapRightShrink, (((3, 3), (6, 9),), 11)),
                (GapChange.GapFill, (((6, 9),), 11)),
                (GapChange.GapRightShrink, (((6, 8),), 11)),
                (GapChange.GapRightShrink, (((6, 7),), 11)),
                (GapChange.GapRightShrink, (((6, 6),), 11)),
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


@given(st.lists(
    st.tuples(
        # True to insert a header (ie~ remove a gap), False to remove a header (ie~ add a gap)
        st.booleans(),
        st.integers(min_value=1, max_value=19),  # constrain to try to cause collisions
    )
))
@example([(True, 2), (True, 4), (False, 4)])
def test_gap_continuity(changes):
    MAX_BLOCK_NUM = 21

    # method to get all the block numbers that are in a gap right now
    _all_missing = compose(set, partial(_all_gap_numbers, highest_block_number=MAX_BLOCK_NUM))

    @to_set
    def _all_inserted(chain_gaps):
        """List all the inserted headers, the block numbers not in gaps"""
        missing = _all_missing(chain_gaps)
        for block_num in range(MAX_BLOCK_NUM + 1):
            if block_num not in missing:
                yield block_num

    chain_gaps = GENESIS_CHAIN_GAPS

    for do_insert, block_num in changes:
        starts_inserted = _all_inserted(chain_gaps)
        starts_missing = _all_missing(chain_gaps)

        if do_insert:
            to_insert = block_num
            _, chain_gaps = fill_gap(to_insert, chain_gaps)
            assert not is_block_number_in_gap(to_insert, chain_gaps)

            # Make sure that at most this one block number was filled
            finished_inserted = _all_inserted(chain_gaps)
            assert to_insert in finished_inserted
            new_inserts = finished_inserted - starts_inserted
            if block_num in starts_inserted:
                assert new_inserts == set()
            else:
                assert new_inserts == {block_num}

            # Make sure that no new gaps were created
            finished_missing = _all_missing(chain_gaps)
            assert to_insert not in finished_missing
            new_missing = finished_missing - starts_missing
            assert new_missing == set()
        else:
            to_remove = block_num
            # Note that removing a header is inserting a gap
            chain_gaps = reopen_gap(to_remove, chain_gaps)
            assert is_block_number_in_gap(to_remove, chain_gaps)

            # Make sure that no gaps were filled
            finished_inserted = _all_inserted(chain_gaps)
            new_inserts = finished_inserted - starts_inserted
            assert new_inserts == set()

            # Make sure that at most this one block number gap was reopened
            finished_missing = _all_missing(chain_gaps)
            new_missing = finished_missing - starts_missing
            if block_num in starts_missing:
                assert new_missing == set()
            else:
                assert new_missing == {block_num}

        _validate_gap_invariants(chain_gaps)


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
