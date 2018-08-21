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
    request_class = GetBlockHeadersRequest

    async def __call__(  # type: ignore
            self,
            block_number_or_hash: BlockIdentifier,
            max_headers: int = None,
            skip: int = 0,
            reverse: bool = True,
            timeout: int = None) -> Tuple[BlockHeader, ...]:

        original_request_args = (block_number_or_hash, max_headers, skip, reverse)
        validator = GetBlockHeadersValidator(*original_request_args)
        request = self.request_class(*original_request_args)

        return await self.get_result(
            request,
            self._normalizer,
            validator,
            noop_payload_validator,
            timeout,
        )


BaseNodeDataExchange = BaseExchange[Tuple[Hash32, ...], Tuple[bytes, ...], NodeDataBundles]


class GetNodeDataExchange(BaseNodeDataExchange):
    _normalizer = GetNodeDataNormalizer()
    request_class = GetNodeDataRequest

    async def __call__(self, node_hashes: Tuple[Hash32, ...]) -> NodeDataBundles:  # type: ignore
        validator = GetNodeDataValidator(node_hashes)
        request = self.request_class(node_hashes)
        return await self.get_result(request, self._normalizer, validator, noop_payload_validator)


class GetReceiptsExchange(BaseExchange[Tuple[Hash32, ...], ReceiptsByBlock, ReceiptsBundles]):
    _normalizer = ReceiptsNormalizer()
    request_class = GetReceiptsRequest

    async def __call__(self, headers: Tuple[BlockHeader, ...]) -> ReceiptsBundles:  # type: ignore
        validator = ReceiptsValidator(headers)

        block_hashes = tuple(header.hash for header in headers)
        request = self.request_class(block_hashes)

        return await self.get_result(request, self._normalizer, validator, noop_payload_validator)


BaseGetBlockBodiesExchange = BaseExchange[
    Tuple[Hash32, ...],
    Tuple[BlockBody, ...],
    BlockBodyBundles,
]


class GetBlockBodiesExchange(BaseGetBlockBodiesExchange):
    _normalizer = GetBlockBodiesNormalizer()
    request_class = GetBlockBodiesRequest

    async def __call__(self, headers: Tuple[BlockHeader, ...]) -> BlockBodyBundles:  # type: ignore
        validator = GetBlockBodiesValidator(headers)

        block_hashes = tuple(header.hash for header in headers)
        request = self.request_class(block_hashes)

        return await self.get_result(request, self._normalizer, validator, noop_payload_validator)
