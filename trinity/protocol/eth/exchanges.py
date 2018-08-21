from typing import (
    Any,
    Dict,
    Tuple,
)

from eth_typing import (
    BlockIdentifier,
    Hash32,
)
from eth.rlp.headers import BlockHeader

from trinity.protocol.common.exchanges import (
    BaseExchange,
)
from trinity.protocol.common.normalizers import (
    NoopNormalizer,
)
from trinity.protocol.common.validators import (
    noop_payload_validator,
)
from trinity.protocol.common.types import (
    BlockBodyBundles,
    NodeDataBundles,
    ReceiptsByBlock,
    ReceiptsBundles,
)
from trinity.rlp.block_body import BlockBody

from .normalizers import (
    GetBlockBodiesNormalizer,
    GetNodeDataNormalizer,
    ReceiptsNormalizer,
)
from .requests import (
    GetBlockBodiesRequest,
    GetBlockHeadersRequest,
    GetNodeDataRequest,
    GetReceiptsRequest,
)
from .validators import (
    GetBlockBodiesValidator,
    GetBlockHeadersValidator,
    GetNodeDataValidator,
    ReceiptsValidator,
)

BaseGetBlockHeadersExchange = BaseExchange[
    Dict[str, Any],
    Tuple[BlockHeader, ...],
    Tuple[BlockHeader, ...],
]


class GetBlockHeadersExchange(BaseGetBlockHeadersExchange):
    _normalizer = NoopNormalizer[Tuple[BlockHeader, ...]]()

    async def __call__(  # type: ignore
            self,
            block_number_or_hash: BlockIdentifier,
            max_headers: int = None,
            skip: int = 0,
            reverse: bool = True) -> Tuple[BlockHeader, ...]:

        original_request_args = (block_number_or_hash, max_headers, skip, reverse)
        validator = GetBlockHeadersValidator(*original_request_args)
        request = GetBlockHeadersRequest(*original_request_args)

        return await self.get_result(request, self._normalizer, validator, noop_payload_validator)


BaseNodeDataExchange = BaseExchange[Tuple[Hash32, ...], Tuple[bytes, ...], NodeDataBundles]


class GetNodeDataExchange(BaseNodeDataExchange):
    _normalizer = GetNodeDataNormalizer()

    async def __call__(self, node_hashes: Tuple[Hash32, ...]) -> NodeDataBundles:  # type: ignore
        validator = GetNodeDataValidator(node_hashes)
        request = GetNodeDataRequest(node_hashes)
        return await self.get_result(request, self._normalizer, validator, noop_payload_validator)


class GetReceiptsExchange(BaseExchange[Tuple[Hash32, ...], ReceiptsByBlock, ReceiptsBundles]):
    _normalizer = ReceiptsNormalizer()

    async def __call__(self, headers: Tuple[BlockHeader, ...]) -> ReceiptsBundles:  # type: ignore
        validator = ReceiptsValidator(headers)

        block_hashes = tuple(header.hash for header in headers)
        request = GetReceiptsRequest(block_hashes)

        return await self.get_result(request, self._normalizer, validator, noop_payload_validator)


BaseGetBlockBodiesExchange = BaseExchange[
    Tuple[Hash32, ...],
    Tuple[BlockBody, ...],
    BlockBodyBundles,
]


class GetBlockBodiesExchange(BaseGetBlockBodiesExchange):
    _normalizer = GetBlockBodiesNormalizer()

    async def __call__(self, headers: Tuple[BlockHeader, ...]) -> BlockBodyBundles:  # type: ignore
        validator = GetBlockBodiesValidator(headers)

        block_hashes = tuple(header.hash for header in headers)
        request = GetBlockBodiesRequest(block_hashes)

        return await self.get_result(request, self._normalizer, validator, noop_payload_validator)
