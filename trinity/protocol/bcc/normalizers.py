from typing import (
    Tuple,
)

import ssz

from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
    BeaconBlock,
)

from trinity.protocol.common.normalizers import BaseNormalizer

from trinity.protocol.bcc.commands import (
    BeaconBlocksMessage,
)


class BeaconBlocksNormalizer(BaseNormalizer[BeaconBlocksMessage, Tuple[BaseBeaconBlock, ...]]):
    @staticmethod
    def normalize_result(message: BeaconBlocksMessage) -> Tuple[BaseBeaconBlock, ...]:
        result = tuple(ssz.decode(block, BeaconBlock) for block in message["encoded_blocks"])
        return result
