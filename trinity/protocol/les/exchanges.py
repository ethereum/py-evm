from typing import (
    Tuple,
    TypeVar,
)

from eth_typing import BlockIdentifier
from eth.abc import BlockHeaderAPI

from p2p.exchange import (
    BaseExchange,
)
from trinity._utils.les import (
    gen_request_id,
)

from .commands import (
    BlockHeaders,
    GetBlockHeaders,
)
from .normalizers import (
    BlockHeadersNormalizer,
)
from .payloads import (
    BlockHeadersQuery,
    GetBlockHeadersPayload,
)
from .trackers import (
    GetBlockHeadersTracker,
)
from .validators import (
    GetBlockHeadersValidator,
    match_payload_request_id,
)

TResult = TypeVar('TResult')


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

        query = BlockHeadersQuery(
            block_number_or_hash=block_number_or_hash,
            max_headers=max_headers,
            skip=skip,
            reverse=reverse,
        )
        payload = GetBlockHeadersPayload(
            request_id=gen_request_id(),
            query=query,
        )
        request = GetBlockHeaders(payload)

        return tuple(await self.get_result(
            request,
            self._normalizer,
            validator,
            match_payload_request_id,
            timeout,
        ))
