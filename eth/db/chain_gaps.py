import enum
from typing import Tuple

from eth_typing import BlockNumber

from eth.exceptions import GapTrackingCorrupted
from eth.typing import BlockRange


class GapChange(enum.Enum):

    NoChange = enum.auto()
    NewGap = enum.auto()
    GapSplit = enum.auto()
    GapShrink = enum.auto()
    TailWrite = enum.auto()


GapInfo = Tuple[GapChange, Tuple[BlockRange, ...]]


def calculate_gaps(newly_persisted: BlockNumber, base_gaps: Tuple[BlockRange, ...]) -> GapInfo:

    # If we have a fresh chain, our highest missing number can only be 1
    highest_missing_number = 1 if base_gaps == () else base_gaps[-1][0]

    if newly_persisted == highest_missing_number:
        # This is adding a consecutive header at the very tail
        new_last_marker = (newly_persisted + 1, -1)
        new_gaps = base_gaps[:-1] + (new_last_marker,)
        gap_change = GapChange.TailWrite
    elif newly_persisted > highest_missing_number:
        # We are creating a gap in the chain
        gap_end = newly_persisted - 1
        new_tail = ((highest_missing_number, gap_end), (newly_persisted + 1, -1),)
        new_gaps = base_gaps[:-1] + new_tail
        gap_change = GapChange.NewGap
    elif newly_persisted < highest_missing_number:
        # We are patching a gap which may either shrink an existing gap or divide it
        matching_gaps = [
            (index, pair) for index, pair in enumerate(base_gaps)
            if newly_persisted >= pair[0] and newly_persisted <= pair[1]
        ]

        if len(matching_gaps) > 1:
            raise GapTrackingCorrupted(
                "Corrupted chain gap tracking",
                f"No {newly_persisted} appears to be missing in multiple gaps",
                f"1st gap goes from {matching_gaps[0][1][0]} to {matching_gaps[0][1][1]}"
                f"2nd gap goes from {matching_gaps[1][1][0]} to {matching_gaps[1][1][1]}"
            )
        elif len(matching_gaps) == 0:
            # Looks like we are just overwriting an existing header.
            return GapChange.NoChange, base_gaps
        elif len(matching_gaps) == 1:
            gap_index, gap = matching_gaps[0]
            if newly_persisted == gap[0] and newly_persisted == gap[1]:
                updated_center: Tuple[Tuple[int, int], ...] = ()
                gap_change = GapChange.GapShrink
            elif newly_persisted == gap[0]:
                # we are shrinking the gap at the start
                updated_center = ((gap[0] + 1, gap[1],),)
                gap_change = GapChange.GapShrink
            elif newly_persisted == gap[1]:
                # we are shrinking the gap at the tail
                updated_center = ((gap[0], gap[1] - 1,),)
                gap_change = GapChange.GapShrink
            else:
                # we are dividing the gap
                first_new_gap = (gap[0], newly_persisted - 1)
                second_new_gap = (newly_persisted + 1, gap[1])
                updated_center = (first_new_gap, second_new_gap,)
                gap_change = GapChange.GapSplit

            before_gap = base_gaps[:gap_index]
            after_gap = base_gaps[gap_index + 1:]
            new_gaps = before_gap + updated_center + after_gap

    else:
        raise Exception("Invariant")

    return gap_change, new_gaps
