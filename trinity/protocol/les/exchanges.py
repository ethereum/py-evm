from typing import (
    Any,
    Dict,
    Tuple,
    TypeVar,
)

from eth_typing import BlockIdentifier, Hash32
from eth.rlp.headers import BlockHeader

from trinity.protocol.common.exchanges import (
    BaseExchange,
)
from trinity.protocol.common.types import NodeDataBundles
from trinity.utils.les import (
    gen_request_id,
)

from .normalizers import (
    BlockHeadersNormalizer,
    GetNodeDataNormalizer)
from .requests import (
    GetBlockHeadersRequest,
    GetNodeDataRequest)
from .trackers import (
    GetBlockHeadersTracker,
    GetNodeDataTracker)
from .validators import (
    GetBlockHeadersValidator,
    match_payload_request_id,
    GetNodeDataValidator)

TResult = TypeVar('TResult')


LESExchange = BaseExchange[Dict[str, Any], Dict[str, Any], TResult]


class GetBlockHeadersExchange(LESExchange[Tuple[BlockHeader, ...]]):
    _normalizer = BlockHeadersNormalizer()
    request_class = GetBlockHeadersRequest
    tracker_class = GetBlockHeadersTracker

    async def __call__(  # type: ignore
            self,
            block_number_or_hash: BlockIdentifier,
            max_headers: int = None,
            skip: int = 0,
            reverse: bool = True,
            timeout: float = None) -> Tuple[BlockHeader, ...]:

        original_request_args = (block_number_or_hash, max_headers, skip, reverse)
        validator = GetBlockHeadersValidator(*original_request_args)

        command_args = original_request_args + (gen_request_id(),)
        request = self.request_class(*command_args)  # type: ignore

        return await self.get_result(
            request,
            self._normalizer,
            validator,
            match_payload_request_id,
            timeout,
        )


class GetNodeDataExchange(LESExchange[Tuple[NodeDataBundles]]):
    _normalizer = GetNodeDataNormalizer()
    request_class = GetNodeDataRequest
    tracker_class = GetNodeDataTracker

    async def __call__(self,  # type: ignore
                       node_hashes: Tuple[Hash32, ...],
                       timeout: float = None) -> NodeDataBundles:
        validator = GetNodeDataValidator(node_hashes)
        request = self.request_class(node_hashes, gen_request_id())
        return await self.get_result(
            request,
            self._normalizer,
            validator,
            match_payload_request_id,
            timeout,
        )
