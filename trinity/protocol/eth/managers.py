from typing import (
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
    BaseRequestManager,
)

from .commands import (
    BlockHeaders,
)
from .requests import HeaderRequest

if TYPE_CHECKING:
    from .peer import ETHPeer  # noqa: F401


class GetBlockHeadersRequestManager(BaseRequestManager['ETHPeer', HeaderRequest, Tuple[BlockHeader, ...], Tuple[BlockHeader, ...]]):
    msg_queue_maxsize = 100

    _response_msg_type: Type[Command] = BlockHeaders

    async def __call__(self,
                       block_number_or_hash: BlockIdentifier,
                       max_headers: int = None,
                       skip: int = 0,
                       reverse: bool = True,
                       timeout: int = None) -> Tuple[BlockHeader, ...]:
        request = HeaderRequest(
            block_number_or_hash,
            max_headers,
            skip,
            reverse,
        )
        return await self._request_and_wait(request, timeout)

    def _send_sub_proto_request(self, request: HeaderRequest) -> None:
        self._peer.sub_proto.send_get_block_headers(request)

    def _normalize_response(self, response: Tuple[BlockHeader, ...]) -> Tuple[BlockHeader, ...]:
        return response
