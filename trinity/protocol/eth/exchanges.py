from typing import (
    Sequence,
    Tuple,
)

from eth_typing import (
    BlockIdentifier,
    Hash32,
)
from eth.abc import BlockHeaderAPI

from p2p.exchange import (
    BaseExchange,
    noop_payload_validator,
)
from trinity.protocol.common.payloads import (
    BlockHeadersQuery,
)
from trinity.protocol.common.typing import (
    BlockBodyBundles,
    NodeDataBundles,
    ReceiptsBundles,
)

from .commands import (
    BlockBodies,
    BlockHeaders,
    GetBlockBodies,
    GetBlockHeaders,
    GetNodeData,
    GetReceipts,
    NodeData,
    Receipts,
)
from .normalizers import (
    BlockHeadersNormalizer,
    GetBlockBodiesNormalizer,
    GetNodeDataNormalizer,
    ReceiptsNormalizer,
)
from .trackers import (
    GetBlockHeadersTracker,
    GetBlockBodiesTracker,
    GetNodeDataTracker,
    GetReceiptsTracker
)
from .validators import (
    GetBlockBodiesValidator,
    GetBlockHeadersValidator,
    GetNodeDataValidator,
    ReceiptsValidator,
)

BaseGetBlockHeadersExchange = BaseExchange[
    GetBlockHeaders,
    BlockHeaders,
    Tuple[BlockHeaderAPI, ...],
]


class GetBlockHeadersExchange(BaseGetBlockHeadersExchange):
    _normalizer = BlockHeadersNormalizer()
    tracker_class = GetBlockHeadersTracker

    _request_command_type = GetBlockHeaders
    _response_command_type = BlockHeaders

    async def __call__(  # type: ignore
            self,
            block_number_or_hash: BlockIdentifier,
            max_headers: int = None,
            skip: int = 0,
            reverse: bool = True,
            timeout: float = None) -> Tuple[BlockHeaderAPI, ...]:

        original_request_args = (block_number_or_hash, max_headers, skip, reverse)
        validator = GetBlockHeadersValidator(*original_request_args)
        request = GetBlockHeaders(BlockHeadersQuery(*original_request_args))

        return await self.get_result(
            request,
            self._normalizer,
            validator,
            noop_payload_validator,
            timeout,
        )


BaseNodeDataExchange = BaseExchange[GetNodeData, NodeData, NodeDataBundles]


class GetNodeDataExchange(BaseNodeDataExchange):
    _normalizer = GetNodeDataNormalizer()
    tracker_class = GetNodeDataTracker

    _request_command_type = GetNodeData
    _response_command_type = NodeData

    async def __call__(self,  # type: ignore
                       node_hashes: Sequence[Hash32],
                       timeout: float = None) -> NodeDataBundles:
        validator = GetNodeDataValidator(node_hashes)
        request = GetNodeData(tuple(node_hashes))
        return await self.get_result(
            request,
            self._normalizer,
            validator,
            noop_payload_validator,
            timeout,
        )


class GetReceiptsExchange(BaseExchange[GetReceipts, Receipts, ReceiptsBundles]):
    _normalizer = ReceiptsNormalizer()
    tracker_class = GetReceiptsTracker

    _request_command_type = GetReceipts
    _response_command_type = Receipts

    async def __call__(self,  # type: ignore
                       headers: Sequence[BlockHeaderAPI],
                       timeout: float = None) -> ReceiptsBundles:
        validator = ReceiptsValidator(headers)

        block_hashes = tuple(header.hash for header in headers)
        request = GetReceipts(block_hashes)

        return await self.get_result(
            request,
            self._normalizer,
            validator,
            noop_payload_validator,
            timeout,
        )


BaseGetBlockBodiesExchange = BaseExchange[
    GetBlockBodies,
    BlockBodies,
    BlockBodyBundles,
]


class GetBlockBodiesExchange(BaseGetBlockBodiesExchange):
    _normalizer = GetBlockBodiesNormalizer()
    tracker_class = GetBlockBodiesTracker

    _request_command_type = GetBlockBodies
    _response_command_type = BlockBodies

    async def __call__(self,  # type: ignore
                       headers: Sequence[BlockHeaderAPI],
                       timeout: float = None) -> BlockBodyBundles:
        validator = GetBlockBodiesValidator(headers)

        block_hashes = tuple(header.hash for header in headers)
        request = GetBlockBodies(block_hashes)

        return await self.get_result(
            request,
            self._normalizer,
            validator,
            noop_payload_validator,
            timeout,
        )
