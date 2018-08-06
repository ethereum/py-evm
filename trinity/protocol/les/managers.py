from typing import (
    Any,
    Dict,
    Tuple,
    Type,
    TYPE_CHECKING,
)

from eth_typing import BlockIdentifier

from eth.rlp.headers import BlockHeader

from p2p.protocol import (
    Command,
)

from trinity.protocol.common.managers import (
    BaseRequestManager as _BaseRequestManager,
)
from trinity.utils.les import (
    gen_request_id,
)

from .commands import (
    BlockHeaders,
)
from .requests import HeaderRequest

if TYPE_CHECKING:
    from .peer import LESPeer  # noqa: #401


BaseRequestManager = _BaseRequestManager[
    'LESPeer',
    HeaderRequest,
    Dict[str, Any],
    Tuple[BlockHeader, ...]
]


class GetBlockHeadersRequestManager(BaseRequestManager):
    msg_queue_maxsize = 100

    _response_msg_type: Type[Command] = BlockHeaders

    # All `RequestManager` classes are expected to implement the `__call__`
    # method, including changing the function signature, thus the
    # `# type: ignore` here is both expected and required.
    async def __call__(self,  # type: ignore
                       block_number_or_hash: BlockIdentifier,
                       max_headers: int = None,
                       skip: int = 0,
                       reverse: bool = True,
                       timeout: int = None) -> Tuple[BlockHeader, ...]:
        request_id = gen_request_id()
        request = HeaderRequest(
            block_number_or_hash,
            max_headers,
            skip,
            reverse,
            request_id,
        )
        return await self._request_and_wait(request, timeout)

    def _send_sub_proto_request(self, request: HeaderRequest) -> None:
        self._peer.sub_proto.send_get_block_headers(request)

    def _normalize_response(self, response: Dict[str, Any]) -> Tuple[BlockHeader, ...]:
        return response['headers']
