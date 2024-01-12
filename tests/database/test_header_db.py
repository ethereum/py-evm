import enum
from functools import (
    partial,
)
import operator
import random

from eth_utils import (
    ValidationError,
    keccak,
    to_set,
    to_tuple,
)
from eth_utils.toolz import (
    accumulate,
    compose,
    sliding_window,
)
from hypothesis import (
    example,
    given,
    settings,
    strategies as st,
)
import pytest

from eth.constants import (
    GENESIS_BLOCK_NUMBER,
    GENESIS_DIFFICULTY,
    GENESIS_GAS_LIMIT,
)
from eth.db.atomic import (
    AtomicDB,
)
from eth.db.chain_gaps import (
    GENESIS_CHAIN_GAPS,
    GapChange,
    fill_gap,
    is_block_number_in_gap,
    reopen_gap,
)
from eth.db.header import (
    HeaderDB,
)
from eth.exceptions import (
    CanonicalHeadNotFound,
    CheckpointsMustBeCanonical,
    GapTrackingCorrupted,
    HeaderNotFound,
    ParentNotFound,
)
from eth.tools.rlp import (
    assert_headers_eq,
)
from eth.vm.forks.gray_glacier import (
    GrayGlacierVM,
)
from eth.vm.forks.gray_glacier.blocks import (
    GrayGlacierBlockHeader as BlockHeader,
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
        # TODO test a variety of chain configs, where transitions to london
        # happen during "interesting" times of the tests
        next_header = GrayGlacierVM.create_header_from_parent(
            previous_header,
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

    headers_from_pseudo_genesis = (
        headers[8],
        headers[9],
    )

    headerdb.persist_header_chain(
        headers_from_pseudo_genesis, pseudo_genesis.parent_hash
    )
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


def _validate_consecutive_canonical_links(headerdb, through_block_number):
    # Validate at every step that there are no two contiguous headers which are both:
    #   - canonical
    #   - mismatched parent/child
    for parent_num, child_num in sliding_window(2, range(0, through_block_number + 1)):
        try:
            parent = headerdb.get_canonical_block_header_by_number(parent_num)
        except HeaderNotFound:
            # no canonical parent, move on...
            continue
        else:
            try:
                child = headerdb.get_canonical_block_header_by_number(child_num)
            except HeaderNotFound:
                # no canonical child, move on...
                continue
            else:
                # Both parent and child are canonical, so they must be parent/child
                assert child.parent_hash == parent.hash


def _validate_gap_invariants(gaps):
    # 1. gaps are sorted
    for low, high in gaps[0]:
        assert high >= low, gaps

    # 2. gaps are not overrlapping
    for low_range, high_range in sliding_window(2, gaps[0]):
        # the top of the low range must not be sequential
        # with the bottom of the high range
        assert low_range[1] + 1 < high_range[0], gaps

    # 3. final gap does not overlap with the tail
    if len(gaps[0]):
        final_gap_range = gaps[0][-1]
        assert final_gap_range[1] + 1 < gaps[1], gaps


@pytest.mark.parametrize(
    "steps",
    (
        # Make sure children of old canonical headers also get de-canonicalized
        (
            (StepAction.PERSIST_HEADERS, ("b", lambda headers: headers[:4])),
            (StepAction.VERIFY_GAPS, ((), 5)),
            # If a header has enough difficulty, be sure to de-canonicalize the old
            # children. In an old implementation, only headers at the same block
            # number were de-canonicalized
            (
                StepAction.PERSIST_HEADERS,
                (
                    "a",
                    # Insert a huge-difficulty header, enough to make sure
                    # all of b gets over-taken
                    lambda headers: [
                        headers[0].copy(difficulty=headers[0].difficulty * 10)
                    ],
                ),
            ),
            (StepAction.VERIFY_GAPS, ((), 2)),
        ),
        # If trying to de-canonicalize children of old canonical headers, and the first
        # child is a checkpoint, then raise an exception.
        (
            (StepAction.PERSIST_HEADERS, ("a", lambda headers: headers[:1])),
            (StepAction.PERSIST_CHECKPOINT, 2),
            (StepAction.VERIFY_GAPS, ((), 3)),
            # If a header has enough difficulty, be sure to de-canonicalize the
            # old children. In an old implementation, only headers at the same block
            # number were de-canonicalized
            # BUT, if one of those children is a checkpoint, then fail hard
            (
                StepAction.VERIFY_PERSIST_RAISES,
                (
                    "b",
                    CheckpointsMustBeCanonical,
                    # Insert a huge-difficulty header, enough to make sure all of a gets
                    # over-taken
                    lambda headers: [
                        headers[0].copy(difficulty=headers[0].difficulty * 10)
                    ],
                ),
            ),
        ),
        # If trying to de-canonicalize children of old canonical headers, and a
        # grandchild is a checkpoint, then raise an exception.
        (
            (StepAction.PERSIST_HEADERS, ("a", lambda headers: headers[:2])),
            (StepAction.PERSIST_CHECKPOINT, 3),
            (StepAction.VERIFY_GAPS, ((), 4)),
            # If a header has enough difficulty, be sure to de-canonicalize the old
            # children. In an old implementation, only headers at the same block number
            # were de-canonicalized
            # BUT, if one of those children is a checkpoint, then fail hard
            (
                StepAction.VERIFY_PERSIST_RAISES,
                (
                    "b",
                    CheckpointsMustBeCanonical,
                    # Insert a huge-difficulty header, enough to make sure all of a gets
                    # over-taken
                    lambda headers: [
                        headers[0].copy(difficulty=headers[0].difficulty * 10)
                    ],
                ),
            ),
        ),
        # If a gap gets filled with a checkpoint, make sure that the checkpoint's parent
        # is valid. Otherwise, decanonicalize and re-insert a gap.
        (
            (StepAction.PERSIST_CHECKPOINT, 4),
            (StepAction.VERIFY_GAPS, (((1, 3),), 5)),
            (StepAction.PERSIST_HEADERS, ("b", lambda headers: headers[:2])),
            (StepAction.VERIFY_GAPS, (((3, 3),), 5)),
            (StepAction.PERSIST_CHECKPOINT, 3),
            (StepAction.VERIFY_GAPS, (((2, 2),), 5)),
            (StepAction.PERSIST_CHECKPOINT, 2),
            (StepAction.VERIFY_GAPS, (((1, 1),), 5)),
            (StepAction.PERSIST_CHECKPOINT, 1),
            (StepAction.VERIFY_GAPS, ((), 5)),
        ),
        # Make sure that b can't sneak it's way to canonical
        (
            (StepAction.PERSIST_HEADERS, ("b", lambda headers: headers[:5])),
            (StepAction.PERSIST_CHECKPOINT, 9),
            (StepAction.PERSIST_CHECKPOINT, 6),
            (StepAction.PERSIST_CHECKPOINT, 1),
            (StepAction.PERSIST_CHECKPOINT, 4),
            (StepAction.VERIFY_GAPS, (((2, 3), (5, 5), (7, 8)), 10)),
            (
                StepAction.VERIFY_PERSIST_RAISES,
                ("b", CheckpointsMustBeCanonical, lambda headers: headers[5:7]),
            ),
        ),
        # Start patching gap with uncles, later overwrite with true chain
        (
            (StepAction.PERSIST_CHECKPOINT, 8),
            (StepAction.VERIFY_GAPS, (((1, 7),), 9)),
            (StepAction.VERIFY_CANONICAL_HEAD, 8),
            (StepAction.PERSIST_HEADERS, ("b", lambda headers: headers[:3])),
            (StepAction.VERIFY_GAPS, (((4, 7),), 9)),
            (StepAction.VERIFY_CANONICAL_HEADERS, ("b", lambda headers: headers[:3])),
            # Verify patching the gap does not affect what our current head is
            (StepAction.VERIFY_CANONICAL_HEAD, 8),
            (StepAction.PERSIST_HEADERS, ("a", lambda headers: headers)),
            # It's important to verify all headers of a became canonical because there
            # was a point in time where the chain "thought" we already had filled 1 - 3
            # but they later turned out to be uncles.
            (StepAction.VERIFY_CANONICAL_HEADERS, ("a", lambda headers: headers)),
            (StepAction.VERIFY_GAPS, ((), 11)),
        ),
        # Writing to the tail end of a gap, when its child would not have a matching
        # parent_hash should raise a validation error
        (
            (StepAction.PERSIST_CHECKPOINT, 4),
            (StepAction.PERSIST_HEADERS, ("b", lambda headers: headers[:2])),
            (StepAction.VERIFY_GAPS, (((3, 3),), 5)),
            (StepAction.PERSIST_CHECKPOINT, 1),
            (StepAction.VERIFY_GAPS, (((2, 3),), 5)),
            # Cannot fill the end of the (2, 3) gap because it doesn't match the
            # checkpoint at 4
            (
                StepAction.VERIFY_PERSIST_RAISES,
                ("b", CheckpointsMustBeCanonical, lambda h: h[2:3]),
            ),
        ),
        # Make sure b can't sneak into canonical, overwriting a checkpoint
        (
            (StepAction.PERSIST_CHECKPOINT, 5),
            (StepAction.PERSIST_HEADERS, ("b", lambda headers: headers[:2])),
            (StepAction.VERIFY_GAPS, (((3, 4),), 6)),
            (StepAction.PERSIST_CHECKPOINT, 1),
            (StepAction.VERIFY_GAPS, (((2, 4),), 6)),
            (
                StepAction.VERIFY_PERSIST_RAISES,
                ("b", CheckpointsMustBeCanonical, lambda headers: headers[2:3]),
            ),
            (StepAction.VERIFY_GAPS, (((2, 4),), 6)),
        ),
        # A couple cases of invalid checkpoint descendents getting de-canonicalized
        (
            (StepAction.PERSIST_HEADERS, ("b", lambda headers: headers[:4])),
            (StepAction.PERSIST_CHECKPOINT, 4),
            (StepAction.PERSIST_HEADERS, ("a", lambda headers: headers[4:5])),
            (StepAction.PERSIST_CHECKPOINT, 1),
            (StepAction.VERIFY_GAPS, (((2, 3),), 6)),
        ),
        (
            (StepAction.PERSIST_HEADERS, ("b", lambda headers: headers[:4])),
            (StepAction.PERSIST_CHECKPOINT, 2),
            (StepAction.VERIFY_GAPS, (((1, 1),), 3)),
            (StepAction.PERSIST_HEADERS, ("a", lambda headers: headers[2:3])),
            (StepAction.VERIFY_GAPS, (((1, 1),), 4)),
        ),
        # Disallow checkpoints being made non-canonical
        (
            (StepAction.PERSIST_HEADERS, ("b", lambda headers: headers[:4])),
            (StepAction.PERSIST_CHECKPOINT, 4),
            (StepAction.PERSIST_HEADERS, ("a", lambda headers: headers[4:5])),
            (StepAction.PERSIST_CHECKPOINT, 1),
            (
                StepAction.VERIFY_PERSIST_RAISES,
                (
                    "b",
                    CheckpointsMustBeCanonical,
                    lambda headers: headers[4:6],
                ),
            ),
            (
                StepAction.VERIFY_CANONICAL_HEADERS,
                ("a", lambda headers: headers[0:1] + headers[3:5]),
            ),
            (StepAction.VERIFY_GAPS, (((2, 3),), 6)),
        ),
        # Another of ^
        (
            (StepAction.PERSIST_HEADERS, ("b", lambda headers: headers[:1])),
            (StepAction.PERSIST_CHECKPOINT, 2),
            (StepAction.VERIFY_GAPS, (((1, 1),), 3)),
            (
                StepAction.VERIFY_PERSIST_RAISES,
                (
                    "b",
                    CheckpointsMustBeCanonical,
                    lambda headers: headers[1:3],
                ),
            ),
            (StepAction.PERSIST_HEADERS, ("a", lambda headers: headers[:1])),
            (StepAction.VERIFY_GAPS, ((), 3)),
            (StepAction.VERIFY_CANONICAL_HEADERS, ("a", lambda headers: headers[:2])),
        ),
        # Checkpoint a child of an uncle
        (
            (StepAction.PERSIST_HEADERS, ("b", lambda headers: headers[:1])),
            (StepAction.VERIFY_GAPS, ((), 2)),
            (StepAction.PERSIST_CHECKPOINT, 2),
            # Persisting a checkpoint where the parent is not a match should cause the
            # parent to become non-canonical.
            (StepAction.VERIFY_GAPS, (((1, 1),), 3)),
            (StepAction.VERIFY_CANONICAL_HEAD, 2),
            # Fill the uncled gap, the checkpoint (no-op) and the tail
            (StepAction.PERSIST_HEADERS, ("a", lambda headers: headers)),
            # Verify that block 1 gets canonicalized as A
            (StepAction.VERIFY_CANONICAL_HEADERS, ("a", lambda headers: headers)),
            (StepAction.VERIFY_GAPS, ((), 11)),
        ),
        # Don't override a checkpoint by persisting a chain that's a child of a gap
        (
            (StepAction.PERSIST_HEADERS, ("b", lambda headers: headers[:1])),
            (StepAction.PERSIST_CHECKPOINT, 2),
            (StepAction.VERIFY_GAPS, (((1, 1),), 3)),
            (
                StepAction.VERIFY_PERSIST_RAISES,
                ("b", CheckpointsMustBeCanonical, lambda headers: headers[1:3]),
            ),
        ),
        # checkpointing should canonicalize matching parent header chain
        (
            (StepAction.PERSIST_HEADERS, ("a", lambda headers: headers[:2])),
            (StepAction.PERSIST_HEADERS, ("b", lambda headers: headers[:3])),
            (StepAction.PERSIST_CHECKPOINT, 3),
            (StepAction.VERIFY_GAPS, ((), 4)),
            (StepAction.VERIFY_CANONICAL_HEADERS, ("a", lambda headers: headers[:3])),
        ),
        # Can not close gap with uncle chain
        (
            (StepAction.PERSIST_CHECKPOINT, 8),
            (StepAction.VERIFY_GAPS, (((1, 7),), 9)),
            (StepAction.VERIFY_CANONICAL_HEAD, 8),
            (
                StepAction.VERIFY_PERSIST_RAISES,
                ("b", CheckpointsMustBeCanonical, lambda h: h[:7]),
            ),
            (StepAction.VERIFY_GAPS, (((1, 7),), 9)),
        ),
        # Can not fill gaps non-sequentially (backwards from checkpoint)
        (
            (StepAction.PERSIST_CHECKPOINT, 4),
            (StepAction.VERIFY_GAPS, (((1, 3),), 5)),
            (StepAction.VERIFY_CANONICAL_HEAD, 4),
            (
                StepAction.VERIFY_PERSIST_RAISES,
                ("b", ParentNotFound, lambda headers: [headers[2]]),
            ),
            (
                StepAction.VERIFY_PERSIST_RAISES,
                ("a", ParentNotFound, lambda headers: [headers[2]]),
            ),
            (StepAction.VERIFY_GAPS, (((1, 3),), 5)),
        ),
        # Can close gap, when head has advanced from checkpoint header
        (
            (StepAction.PERSIST_CHECKPOINT, 4),
            (StepAction.PERSIST_HEADERS, ("a", lambda headers: [headers[4]])),
            (StepAction.VERIFY_GAPS, (((1, 3),), 6)),
            (StepAction.VERIFY_CANONICAL_HEAD, 5),
            (StepAction.PERSIST_HEADERS, ("a", lambda headers: headers[:3])),
            (StepAction.VERIFY_GAPS, ((), 6)),
        ),
        # Can close gap that ends at checkpoint header
        (
            (StepAction.PERSIST_CHECKPOINT, 4),
            (StepAction.VERIFY_GAPS, (((1, 3),), 5)),
            (StepAction.VERIFY_CANONICAL_HEAD, 4),
            (StepAction.PERSIST_HEADERS, ("a", lambda headers: headers[:3])),
            (StepAction.VERIFY_GAPS, ((), 5)),
        ),
        # Open new gaps, while filling in previous gaps
        (
            (StepAction.PERSIST_CHECKPOINT, 4),
            (StepAction.VERIFY_GAPS, (((1, 3),), 5)),
            (StepAction.VERIFY_CANONICAL_HEAD, 4),
            (StepAction.PERSIST_HEADERS, ("a", lambda headers: headers[:2])),
            (StepAction.VERIFY_GAPS, (((3, 3),), 5)),
            # Create another gap
            (StepAction.PERSIST_CHECKPOINT, 8),
            (StepAction.VERIFY_CANONICAL_HEAD, 8),
            (
                StepAction.VERIFY_GAPS,
                (
                    (
                        (3, 3),
                        (5, 7),
                    ),
                    9,
                ),
            ),
            # Work on the second gap but don't close
            (StepAction.PERSIST_HEADERS, ("a", lambda headers: headers[4:6])),
            (StepAction.VERIFY_GAPS, (((3, 3), (7, 7)), 9)),
            # Close first gap
            (StepAction.PERSIST_HEADERS, ("a", lambda headers: [headers[2]])),
            (StepAction.VERIFY_GAPS, (((7, 7),), 9)),
            # Close second gap
            (StepAction.PERSIST_HEADERS, ("a", lambda headers: [headers[6]])),
            (StepAction.VERIFY_GAPS, ((), 9)),
        ),
    ),
)
def test_different_cases_of_patching_gaps(headerdb, genesis_header, steps):
    headerdb.persist_header(genesis_header)
    new_chain_length = 10
    chain_a = mk_header_chain(genesis_header, length=new_chain_length)
    chain_b = mk_header_chain(genesis_header, length=new_chain_length)

    def _get_chain(id):
        if chain_id == "a":
            return chain_a
        elif chain_id == "b":
            return chain_b
        else:
            raise Exception(f"Invalid chain id: {chain_id}")

    assert headerdb.get_header_chain_gaps() == GENESIS_CHAIN_GAPS

    for _step_index, step in enumerate(
        steps
    ):  # noqa: B007  # step_index only present for debugging
        step_action, step_data = step
        if step_action is StepAction.PERSIST_CHECKPOINT:
            pseudo_genesis = chain_a[step_data - 1]
            pseudo_genesis_score = get_score(genesis_header, chain_a[0:step_data])
            headerdb.persist_checkpoint_header(pseudo_genesis, pseudo_genesis_score)
        elif step_action is StepAction.PERSIST_HEADERS:
            chain_id, selector_fn = step_data
            headers = selector_fn(_get_chain(chain_id))
            headerdb.persist_header_chain(headers)
        elif step_action is StepAction.VERIFY_GAPS:
            gaps = headerdb.get_header_chain_gaps()
            assert gaps == step_data
            all_gap_numbers = _all_gap_numbers(
                gaps, highest_block_number=new_chain_length + 1
            )
            for missing_block_number in all_gap_numbers:
                with pytest.raises(HeaderNotFound):
                    headerdb.get_canonical_block_header_by_number(missing_block_number)
        elif step_action is StepAction.VERIFY_PERSIST_RAISES:
            chain_id, error, selector_fn = step_data
            headers = selector_fn(_get_chain(chain_id))
            with pytest.raises(error):
                headerdb.persist_header_chain(headers)
        elif step_action is StepAction.VERIFY_CANONICAL_HEAD:
            # save actual and expected for easy reading on a failed test
            actual_canonical = headerdb.get_canonical_head()
            expected_canonical = chain_a[step_data - 1]
            assert_headers_eq(actual_canonical, expected_canonical)
        elif step_action is StepAction.VERIFY_CANONICAL_HEADERS:
            chain_id, selector_fn = step_data
            for header in selector_fn(_get_chain(chain_id)):
                assert (
                    headerdb.get_canonical_block_header_by_number(header.block_number)
                    == header
                )
        else:
            raise Exception("Unknown step action")

        _validate_gap_invariants(headerdb.get_header_chain_gaps())
        _validate_consecutive_canonical_links(headerdb, new_chain_length + 1)


@pytest.mark.parametrize(
    "written_headers, evolving_gaps",
    (
        (  # consecutive updates, then overwriting existing header
            (1, 2, 1),
            (
                (GapChange.TailWrite, ((), 2)),
                (GapChange.TailWrite, ((), 3)),
                (GapChange.NoChange, ((), 3)),
            ),
        ),
        (  # consecutive updates
            (1, 2, 3),
            (
                (GapChange.TailWrite, ((), 2)),
                (GapChange.TailWrite, ((), 3)),
                (GapChange.TailWrite, ((), 4)),
            ),
        ),
        (  # missing a single header in the middle
            (1, 3),
            (
                (GapChange.TailWrite, ((), 2)),
                (GapChange.NewGap, (((2, 2),), 4)),
            ),
        ),
        (  # missing three headers in the middle
            (1, 5),
            (
                (GapChange.TailWrite, ((), 2)),
                (GapChange.NewGap, (((2, 4),), 6)),
            ),
        ),
        (  # missing three middle headers, then patching center, dividing existing hole
            (1, 5, 3),
            (
                (GapChange.TailWrite, ((), 2)),
                (GapChange.NewGap, (((2, 4),), 6)),
                (
                    GapChange.GapSplit,
                    (
                        (
                            (2, 2),
                            (4, 4),
                        ),
                        6,
                    ),
                ),
            ),
        ),
        (  # multiple holes, shrinking them until they vanish
            (1, 10, 5, 2, 4, 3, 9, 8, 7, 6),
            (
                (GapChange.TailWrite, ((), 2)),
                (GapChange.NewGap, (((2, 9),), 11)),
                (
                    GapChange.GapSplit,
                    (
                        (
                            (2, 4),
                            (6, 9),
                        ),
                        11,
                    ),
                ),
                (
                    GapChange.GapLeftShrink,
                    (
                        (
                            (3, 4),
                            (6, 9),
                        ),
                        11,
                    ),
                ),
                (
                    GapChange.GapRightShrink,
                    (
                        (
                            (3, 3),
                            (6, 9),
                        ),
                        11,
                    ),
                ),
                (GapChange.GapFill, (((6, 9),), 11)),
                (GapChange.GapRightShrink, (((6, 8),), 11)),
                (GapChange.GapRightShrink, (((6, 7),), 11)),
                (GapChange.GapRightShrink, (((6, 6),), 11)),
                (GapChange.GapFill, ((), 11)),
            ),
        ),
    ),
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


@given(
    st.lists(
        st.tuples(
            # True to insert a header (ie~ remove a gap), False to remove a
            # header (ie~ add a gap)
            st.booleans(),
            st.integers(
                min_value=1, max_value=19
            ),  # constrain to try to cause collisions
        )
    )
)
@example([(True, 2), (True, 4), (False, 4)])
def test_gap_continuity(changes):
    MAX_BLOCK_NUM = 21

    # method to get all the block numbers that are in a gap right now
    _all_missing = compose(
        set, partial(_all_gap_numbers, highest_block_number=MAX_BLOCK_NUM)
    )

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


@given(st.data())
@settings(max_examples=1)
def test_true_chain_canonicalized_regardless_of_order(genesis_header, data):
    class ActionEnum(enum.Enum):
        PERSIST_CHAIN = enum.auto()
        CHECKPOINT = enum.auto()

    # Setup
    headerdb = HeaderDB(AtomicDB())
    CHAIN_A, CHAIN_B = 0, 1
    chain_length = data.draw(st.integers(min_value=2, max_value=20))
    headerdb.persist_header(genesis_header)
    chain_a_headers = mk_header_chain(genesis_header, length=chain_length)
    headers = [
        # chain A: eventually canonical; the only source for checkpoints
        chain_a_headers,
        # chain B: non-canonical
        mk_header_chain(genesis_header, length=chain_length),
    ]
    missing_indices = [
        set(range(chain_length)),  # chain A
        set(range(chain_length)),  # chain B
    ]

    @to_tuple
    def _get_valid_extensions(of_missing_indices):
        """
        Find the headers that have available parents, and so are valid to persist
        """
        # For each chain
        for chain_index, header_indices in enumerate(of_missing_indices):
            # yield each header number that has a parent that's not missing
            # Sorting header_indices is important for hypothesis consistency
            for header_index in sorted(header_indices):
                if header_index == 0 or header_index - 1 not in header_indices:
                    yield (chain_index, header_index)

    last_checkpoint = None

    while len(missing_indices[CHAIN_A]):
        _validate_consecutive_canonical_links(headerdb, chain_length)
        _validate_gap_invariants(headerdb.get_header_chain_gaps())

        action = data.draw(st.sampled_from(ActionEnum))
        if action == ActionEnum.CHECKPOINT:
            checkpoint_index = data.draw(
                st.sampled_from(list(sorted(missing_indices[CHAIN_A])))
            )
            checkpoint = chain_a_headers[checkpoint_index]
            checkpoint_score = get_score(
                genesis_header, chain_a_headers[: checkpoint_index + 1]
            )
            headerdb.persist_checkpoint_header(checkpoint, checkpoint_score)

            # keep track of whether any checkpoints were added, so we eventually
            # guarantee A as canonical
            last_checkpoint = checkpoint_index

            missing_indices[CHAIN_A].discard(checkpoint_index)

        elif action == ActionEnum.PERSIST_CHAIN:
            # choose the series of headers to add
            valid_extensions = _get_valid_extensions(missing_indices)
            chain_idx, next_chain_start = data.draw(st.sampled_from(valid_extensions))
            next_chain_len = data.draw(st.integers(min_value=1, max_value=chain_length))
            chain_range_end = next_chain_start + next_chain_len
            next_headers = headers[chain_idx][next_chain_start:chain_range_end]

            # persist them to chain
            try:
                headerdb.persist_header_chain(next_headers)
            except CheckpointsMustBeCanonical:
                assert (
                    chain_idx == CHAIN_B
                ), "Only chain B should fail to decanonize checkpoint"
                # Persist failed, so retry different action
                continue

            # mark persisted headers as not missing
            for inserted_index in range(next_chain_start, chain_range_end):
                missing_indices[chain_idx].discard(inserted_index)

    _validate_consecutive_canonical_links(headerdb, chain_length)
    _validate_gap_invariants(headerdb.get_header_chain_gaps())

    if last_checkpoint is None:
        # Force canonicalization of chain a by adding a bonus header at the end of
        #   all the chain A headers.
        (subsequent_header,) = mk_header_chain(chain_a_headers[-1], length=1)
        headerdb.persist_checkpoint_header(
            subsequent_header,
            get_score(genesis_header, chain_a_headers + (subsequent_header,)),
        )

        assert_is_canonical_chain(headerdb, chain_a_headers + (subsequent_header,))
    else:
        if headerdb.get_canonical_head() != chain_a_headers[-1]:
            child_headers = mk_header_chain(chain_a_headers[-1], length=1)
            headerdb.persist_header_chain(child_headers)
            assert_is_canonical_chain(headerdb, chain_a_headers + child_headers)
        else:
            assert_is_canonical_chain(headerdb, chain_a_headers)

    _validate_consecutive_canonical_links(headerdb, chain_length)
    _validate_gap_invariants(headerdb.get_header_chain_gaps())


@pytest.mark.parametrize(
    "chain_length",
    (0, 1, 2, 3),
)
def test_headerdb_get_canonical_head_with_header_chain_iterator(
    headerdb, genesis_header, chain_length
):
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
        parent_hash=b"\x0f" * 32,
        timestamp=0,
    )
    with pytest.raises(ParentNotFound, match="unknown parent"):
        headerdb.persist_header(header)


def test_headerdb_persist_header_chain_disallows_non_contiguous_chain(
    headerdb, genesis_header
):
    headerdb.persist_header(genesis_header)

    headers = mk_header_chain(genesis_header, length=3)

    non_contiguous_headers = (
        headers[0],
        headers[2],
        headers[1],
    )

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
        assert res == ()

    for idx, header in enumerate(chain_c, 1):
        res, _ = headerdb.persist_header(header)
        if idx <= 3:
            # prior to passing up `chain_a` each import should not return new
            # canonical headers.
            assert res == ()
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
        canonical = headerdb.get_canonical_block_header_by_number(header.block_number)
        assert canonical == header

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

    # insert `chain_a` into the database and verify that each block becomes the
    # canonical head.
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

        # HEAD should remain at the tip of `chain_a` until *after* the 8th
        # header is imported
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
