import enum
from typing import Tuple

from eth_typing import BlockNumber

from eth.exceptions import GapTrackingCorrupted
from eth.typing import BlockRange, ChainGaps


class GapChange(enum.Enum):
    NoChange = enum.auto()
    NewGap = enum.auto()
    GapFill = enum.auto()
    GapSplit = enum.auto()
    GapShrink = enum.auto()
    TailWrite = enum.auto()


GAP_WRITES = (GapChange.GapFill, GapChange.GapSplit, GapChange.GapShrink)
GENESIS_CHAIN_GAPS = ((), BlockNumber(1))

GapInfo = Tuple[GapChange, ChainGaps]


def calculate_gaps(newly_persisted: BlockNumber, base_gaps: ChainGaps) -> GapInfo:

    current_gaps, tip_child = base_gaps

    if newly_persisted == tip_child:
        # This is adding a consecutive header at the very tail
        new_gaps = (current_gaps, BlockNumber(newly_persisted + 1))
        gap_change = GapChange.TailWrite
    elif newly_persisted > tip_child:
        # We are creating a gap in the chain
        gap_end = BlockNumber(newly_persisted - 1)
        new_gaps = (
            current_gaps + ((tip_child, gap_end),), BlockNumber(newly_persisted + 1)
        )
        gap_change = GapChange.NewGap
    elif newly_persisted < tip_child:
        # We are patching a gap which may either shrink an existing gap or divide it
        matching_gaps = [
            (index, pair) for index, pair in enumerate(current_gaps)
            if newly_persisted >= pair[0] and newly_persisted <= pair[1]
        ]

        if len(matching_gaps) > 1:
            raise GapTrackingCorrupted(
                "Corrupted chain gap tracking",
                f"No. {newly_persisted} appears to be missing in multiple gaps",
                f"1st gap goes from {matching_gaps[0][1][0]} to {matching_gaps[0][1][1]}"
                f"2nd gap goes from {matching_gaps[1][1][0]} to {matching_gaps[1][1][1]}"
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
                updated_center = ((BlockNumber(gap[0] + 1), gap[1],),)
                gap_change = GapChange.GapShrink
            elif newly_persisted == gap[1]:
                # we are shrinking the gap at the tail
                updated_center = ((gap[0], BlockNumber(gap[1] - 1),),)
                gap_change = GapChange.GapShrink
            elif gap[0] < newly_persisted < gap[1]:
                # we are dividing the gap
                first_new_gap = (gap[0], BlockNumber(newly_persisted - 1))
                second_new_gap = (BlockNumber(newly_persisted + 1), gap[1])
                updated_center = (first_new_gap, second_new_gap,)
                gap_change = GapChange.GapSplit
            else:
                raise Exception("Invariant")

            before_gap = current_gaps[:gap_index]
            after_gap = current_gaps[gap_index + 1:]
            new_gaps = (before_gap + updated_center + after_gap, tip_child)

    else:
        raise Exception("Invariant")

    return gap_change, new_gaps
