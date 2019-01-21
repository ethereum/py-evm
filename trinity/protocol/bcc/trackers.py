from typing import (
    Tuple,
)

from eth2.beacon.types.blocks import BaseBeaconBlock

from trinity.protocol.common.trackers import BasePerformanceTracker
from trinity.protocol.bcc.requests import (
    GetBeaconBlocksRequest,
)


class GetBeaconBlocksTracker(BasePerformanceTracker[GetBeaconBlocksRequest,
                                                    Tuple[BaseBeaconBlock, ...]]):

    def _get_request_size(self, request: GetBeaconBlocksRequest) -> int:
        return request.command_payload["max_blocks"]

    def _get_result_size(self, result: Tuple[BaseBeaconBlock, ...]) -> int:
        return len(result)

    def _get_result_item_count(self, result: Tuple[BaseBeaconBlock, ...]) -> int:
        return len(result)
