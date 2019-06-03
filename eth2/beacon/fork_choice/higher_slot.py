from eth2.beacon.types.blocks import BaseBeaconBlock


def higher_slot_scoring(block: BaseBeaconBlock) -> int:
    """
    A ``block`` with a higher slot has a higher score.
    """
    return block.slot
