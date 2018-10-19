from typing import (
    Any,
)

from eth.beacon.types.blocks import (
    BaseBeaconBlock,
)


class SerenityBeaconBlock(BaseBeaconBlock):
    pass


def create_serenity_block_from_parent(parent_block: BaseBeaconBlock,
                                      **block_params: Any) -> BaseBeaconBlock:
    block = BaseBeaconBlock.from_parent(parent_block=parent_block, **block_params)

    return block
