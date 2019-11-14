from typing import (
    Optional,
    Tuple,
)

from eth.abc import BlockHeaderAPI

from p2p.exchange import BasePerformanceTracker

from trinity._utils.headers import sequence_builder

from .commands import (
    GetBlockHeaders,
)


BaseGetBlockHeadersTracker = BasePerformanceTracker[
    GetBlockHeaders,
    Tuple[BlockHeaderAPI, ...],
]


class GetBlockHeadersTracker(BaseGetBlockHeadersTracker):
    def _get_request_size(self, request: GetBlockHeaders) -> Optional[int]:
        payload = request.payload.query
        if isinstance(payload.block_number_or_hash, int):
            return len(sequence_builder(
                start_number=payload.block_number_or_hash,
                max_length=payload.max_headers,
                skip=payload.skip,
                reverse=payload.reverse,
            ))
        else:
            return None

    def _get_result_size(self, result: Tuple[BlockHeaderAPI, ...]) -> int:
        return len(result)

    def _get_result_item_count(self, result: Tuple[BlockHeaderAPI, ...]) -> int:
        return len(result)
