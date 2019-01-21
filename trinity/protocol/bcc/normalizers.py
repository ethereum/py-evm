from typing import (
    Tuple,
)

from eth.beacon.types.blocks import BaseBeaconBlock

from trinity.protocol.common.normalizers import BaseNormalizer

from trinity.protocol.bcc.commands import (
    BeaconBlocksMessage,
)


class BeaconBlocksNormalizer(BaseNormalizer[BeaconBlocksMessage, Tuple[BaseBeaconBlock, ...]]):
    @staticmethod
    def normalize_result(message: BeaconBlocksMessage) -> Tuple[BaseBeaconBlock, ...]:
        result = message["blocks"]
        return result
