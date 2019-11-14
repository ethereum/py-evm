from typing import (
    Optional,
    Tuple,
)

from eth.abc import BlockHeaderAPI

from p2p.exchange import BasePerformanceTracker

from trinity.protocol.common.typing import (
    BlockBodyBundles,
    NodeDataBundles,
    ReceiptsBundles,
)
from trinity._utils.headers import sequence_builder

from .commands import (
    GetBlockBodies,
    GetBlockHeaders,
    GetNodeData,
    GetReceipts,
)


BaseGetBlockHeadersTracker = BasePerformanceTracker[
    GetBlockHeaders,
    Tuple[BlockHeaderAPI, ...],
]


class GetBlockHeadersTracker(BaseGetBlockHeadersTracker):
    def _get_request_size(self, request: GetBlockHeaders) -> int:
        payload = request.payload
        if isinstance(payload.block_number_or_hash, int):
            return len(sequence_builder(
                start_number=payload.block_number_or_hash,
                max_length=payload.max_headers,
                skip=payload.skip,
                reverse=payload.reverse,
            ))
        else:
            return None

    def _get_result_size(self, result: Tuple[BlockHeaderAPI, ...]) -> Optional[int]:
        return len(result)

    def _get_result_item_count(self, result: Tuple[BlockHeaderAPI, ...]) -> int:
        return len(result)


class GetBlockBodiesTracker(BasePerformanceTracker[GetBlockBodies, BlockBodyBundles]):
    def _get_request_size(self, request: GetBlockBodies) -> Optional[int]:
        return len(request.payload)

    def _get_result_size(self, result: BlockBodyBundles) -> int:
        return len(result)

    def _get_result_item_count(self, result: BlockBodyBundles) -> int:
        return sum(
            len(body.uncles) + len(body.transactions)
            for body, trie_data, uncles_hash
            in result
        )


class GetReceiptsTracker(BasePerformanceTracker[GetReceipts, ReceiptsBundles]):
    def _get_request_size(self, request: GetReceipts) -> Optional[int]:
        return len(request.payload)

    def _get_result_size(self, result: ReceiptsBundles) -> int:
        return len(result)

    def _get_result_item_count(self, result: ReceiptsBundles) -> int:
        return sum(
            len(receipts)
            for receipts, trie_data
            in result
        )


class GetNodeDataTracker(BasePerformanceTracker[GetNodeData, NodeDataBundles]):
    def _get_request_size(self, request: GetNodeData) -> Optional[int]:
        return len(request.payload)

    def _get_result_size(self, result: NodeDataBundles) -> int:
        return len(result)

    def _get_result_item_count(self, result: NodeDataBundles) -> int:
        return len(result)
