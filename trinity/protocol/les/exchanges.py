from typing import (
    Any,
    Dict,
    Tuple,
    TYPE_CHECKING,
    TypeVar,
)

from eth_typing import BlockIdentifier
from eth.rlp.headers import BlockHeader
from p2p.exceptions import ValidationError

from trinity.protocol.common.exchanges import (
    BaseExchange,
)
from trinity.utils.les import (
    gen_request_id,
)

from .normalizers import (
    BlockHeadersNormalizer,
)
from .requests import (
    GetBlockHeadersRequest,
)
from .validators import (
    GetBlockHeadersValidator,
)

if TYPE_CHECKING:
    from .peer import LESPeer  # noqa: #401

TResult = TypeVar('TResult')


class LESExchange(BaseExchange[Dict[str, Any], Dict[str, Any], TResult]):
    def _match_message_request_id(self, payload: Dict[str, Any], message: Dict[str, Any]) -> None:
        if payload['request_id'] != message['request_id']:
            raise ValidationError("Request `id` does not match")


class GetBlockHeadersExchange(LESExchange[Tuple[BlockHeader, ...]]):
    _normalizer = BlockHeadersNormalizer()

    async def __call__(  # type: ignore
            self,
            block_number_or_hash: BlockIdentifier,
            max_headers: int = None,
            skip: int = 0,
            reverse: bool = True) -> Tuple[BlockHeader, ...]:

        original_request_args = (block_number_or_hash, max_headers, skip, reverse)
        validator = GetBlockHeadersValidator(*original_request_args)

        command_args = original_request_args + (gen_request_id(),)
        request = GetBlockHeadersRequest(*command_args)

        return await self.get_result(
            request,
            self._normalizer,
            validator,
            self._match_message_request_id,
        )
