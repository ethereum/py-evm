import enum
from typing import (
    Iterable,
    Tuple,
)

from eth_typing import (
    BlockNumber,
)
from eth_utils import (
    ValidationError,
    to_tuple,
)

from eth.exceptions import (
    GapTrackingCorrupted,
)
from eth.typing import (
    BlockRange,
    ChainGaps,
)


class GapChange(enum.Enum):
    NoChange = enum.auto()
    NewGap = enum.auto()
    GapFill = enum.auto()
    GapSplit = enum.auto()
    GapLeftShrink = enum.auto()
    GapRightShrink = enum.auto()
    TailWrite = enum.auto()


GAP_WRITES = (
    GapChange.GapFill,
    GapChange.GapSplit,
    GapChange.GapLeftShrink,
    GapChange.GapRightShrink,
)
GENESIS_CHAIN_GAPS = ((), BlockNumber(1))

GapInfo = Tuple[GapChange, ChainGaps]


@to_tuple
def _join_overlapping_gaps(
    unjoined_gaps: Tuple[BlockRange, ...]
) -> Iterable[BlockRange]:
    """
    After introducing a new gap, join any that overlap.
    Input must already be sorted.
    """
    unyielded_low = None
    unyielded_high = None
    for low, high in unjoined_gaps:
        if unyielded_high is not None:
            if low < unyielded_low:
                raise ValidationError(f"Unsorted input! {unjoined_gaps!r}")
            elif unyielded_low <= low <= unyielded_high + 1:
                unyielded_high = max(high, unyielded_high)
                continue
            else:
                yield unyielded_low, unyielded_high

        unyielded_low = low
        unyielded_high = high

    if unyielded_high is not None:
        yield unyielded_low, unyielded_high


def reopen_gap(decanonicalized: BlockNumber, base_gaps: ChainGaps) -> ChainGaps:
    """
    Add a new gap, for a header that was decanonicalized.
    """
    current_gaps, tip_child = base_gaps

    if tip_child <= decanonicalized:
        return base_gaps

    new_raw_gaps = current_gaps + ((decanonicalized, decanonicalized),)

    # join overlapping gaps
    joined_gaps = _join_overlapping_gaps(sorted(new_raw_gaps))

    # is the last gap overlapping with the tip child? if so, merge it
    if joined_gaps[-1][1] + 1 >= tip_child:
        return joined_gaps[:-1], joined_gaps[-1][0]
    else:
        return joined_gaps, tip_child


def is_block_number_in_gap(block_number: BlockNumber, gaps: ChainGaps) -> bool:
    """
    Check if a block number is found in the given gaps
    """
    gap_ranges, tip_child = gaps
    for low, high in gap_ranges:
        if low > block_number:
            return False
        elif high >= block_number:
            return True
        # this range was below the block number, continue looking at the next range

    return block_number >= tip_child


def fill_gap(newly_persisted: BlockNumber, base_gaps: ChainGaps) -> GapInfo:
    """
    Remove a gap, for a new header that was canonicalized.
    """
    current_gaps, tip_child = base_gaps

    if newly_persisted == tip_child:
        # This is adding a consecutive header at the very tail
        new_gaps = (current_gaps, BlockNumber(newly_persisted + 1))
        gap_change = GapChange.TailWrite
    elif newly_persisted > tip_child:
        # We are creating a gap in the chain
        gap_end = BlockNumber(newly_persisted - 1)
        new_gaps = (
            current_gaps + ((tip_child, gap_end),),
            BlockNumber(newly_persisted + 1),
        )
        gap_change = GapChange.NewGap
    elif newly_persisted < tip_child:
        # We are patching a gap which may either shrink an existing gap or divide it
        matching_gaps = [
            (index, pair)
            for index, pair in enumerate(current_gaps)
            if newly_persisted >= pair[0] and newly_persisted <= pair[1]
        ]

        if len(matching_gaps) > 1:
            first_match, second_match, *_ = matching_gaps
            raise GapTrackingCorrupted(
                "Corrupted chain gap tracking",
                f"No. {newly_persisted} appears to be missing in multiple gaps",
                f"1st gap is {first_match[1]}, 2nd gap is {second_match[1]}",
                f"all matching gaps: {matching_gaps}",
            )
        elif len(matching_gaps) == 0:
            # Looks like we are just overwriting an existing header.
            return GapChange.NoChange, base_gaps
        elif len(matching_gaps) == 1:
            gap_index, gap = matching_gaps[0]
            if newly_persisted == gap[0] and newly_persisted == gap[1]:
                updated_center: Tuple[BlockRange, ...] = ()
                gap_change = GapChange.GapFill
            elif newly_persisted == gap[0]:
                # we are shrinking the gap at the start
                updated_center = (
                    (
                        BlockNumber(gap[0] + 1),
                        gap[1],
                    ),
                )
                gap_change = GapChange.GapLeftShrink
            elif newly_persisted == gap[1]:
                # we are shrinking the gap at the tail
                updated_center = (
                    (
                        gap[0],
                        BlockNumber(gap[1] - 1),
                    ),
                )
                gap_change = GapChange.GapRightShrink
            elif gap[0] < newly_persisted < gap[1]:
                # we are dividing the gap
                first_new_gap = (gap[0], BlockNumber(newly_persisted - 1))
                second_new_gap = (BlockNumber(newly_persisted + 1), gap[1])
                updated_center = (
                    first_new_gap,
                    second_new_gap,
                )
                gap_change = GapChange.GapSplit
            else:
                raise Exception("Invariant")

            before_gap = current_gaps[:gap_index]
            after_gap = current_gaps[gap_index + 1 :]
            new_gaps = (before_gap + updated_center + after_gap, tip_child)

    else:
        raise Exception("Invariant")

    return gap_change, new_gaps
