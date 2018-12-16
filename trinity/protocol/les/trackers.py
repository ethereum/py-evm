from typing import (
    Optional,
    Tuple,
)

from eth.rlp.headers import BlockHeader

from trinity.protocol.common.trackers import BasePerformanceTracker
from trinity.protocol.common.types import NodeDataBundles
from trinity.utils.headers import sequence_builder

from .requests import (
    GetBlockHeadersRequest,
    GetNodeDataRequest)


BaseGetBlockHeadersTracker = BasePerformanceTracker[
    GetBlockHeadersRequest,
    Tuple[BlockHeader, ...],
]


class GetBlockHeadersTracker(BaseGetBlockHeadersTracker):
    def _get_request_size(self, request: GetBlockHeadersRequest) -> Optional[int]:
        payload = request.command_payload['query']
        if isinstance(payload['block_number_or_hash'], int):
            return len(sequence_builder(
                start_number=payload['block_number_or_hash'],
                max_length=payload['max_headers'],
                skip=payload['skip'],
                reverse=payload['reverse'],
            ))
        else:
            return None

    def _get_result_size(self, result: Tuple[BlockHeader, ...]) -> int:
        return len(result)

    def _get_result_item_count(self, result: Tuple[BlockHeader, ...]) -> int:
        return len(result)



BaseNodeDataTracker = BasePerformanceTracker[
    GetNodeDataRequest,
    NodeDataBundles,
]


class GetNodeDataTracker(BaseNodeDataTracker):
    def _get_request_size(self, request: GetNodeDataRequest) -> Optional[int]:
        return len(request.command_payload['block_hashes'])

    def _get_result_size(self, result: NodeDataBundles) -> int:
        return len(result)

    def _get_result_item_count(self, result: NodeDataBundles) -> int:
        return len(result)
