from eth2.beacon.typing import (
    FromBlockParams,
)

from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
    BeaconBlock,
)


class SerenityBeaconBlock(BeaconBlock):
    pass


def create_serenity_block_from_parent(parent_block: BaseBeaconBlock,
                                      block_params: FromBlockParams) -> BaseBeaconBlock:
    block = SerenityBeaconBlock.from_parent(parent_block, block_params)

    return block
