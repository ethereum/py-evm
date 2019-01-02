from typing import (
    Any,
)

from eth.beacon.types.blocks import (
    BaseBeaconBlock,
    BeaconBlock,
    BeaconBlockBody,
)


class SerenityBeaconBlockBody(BeaconBlockBody):
    pass


class SerenityBeaconBlock(BeaconBlock):
    pass


def create_serenity_block_from_parent(parent_block: BaseBeaconBlock,
                                      **block_params: Any) -> BaseBeaconBlock:
    block = SerenityBeaconBlock.from_parent(parent_block=parent_block, **block_params)

    return block
