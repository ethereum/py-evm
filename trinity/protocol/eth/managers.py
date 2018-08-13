from typing import (
    Tuple,
    Type,
    TYPE_CHECKING,
)

from eth_typing import (
    BlockIdentifier,
    Hash32,
)

from eth_hash.auto import keccak

from eth.rlp.headers import BlockHeader

from p2p.exceptions import MalformedMessage
from p2p.protocol import (
    Command,
)

from trinity.protocol.common.managers import (
    BaseRequestManager,
)

from .commands import (
    BlockHeaders,
    NodeData,
)
from .requests import (
    HeaderRequest,
    NodeDataRequest,
)

if TYPE_CHECKING:
    from .peer import ETHPeer  # noqa: F401


BaseGetBlockHeadersRequestManager = BaseRequestManager[
    'ETHPeer',
    HeaderRequest,
    Tuple[BlockHeader, ...],
    Tuple[BlockHeader, ...],
]


class GetBlockHeadersRequestManager(BaseGetBlockHeadersRequestManager):
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
        request = HeaderRequest(
            block_number_or_hash,
            max_headers,
            skip,
            reverse,
        )
        return await self._request_and_wait(request, timeout)

    def _send_sub_proto_request(self, request: HeaderRequest) -> None:
        self._peer.sub_proto.send_get_block_headers(request)

    async def _normalize_response(self,
                                  msg: Tuple[BlockHeader, ...]
                                  ) -> Tuple[BlockHeader, ...]:
        return msg

    def _get_item_count(self, msg: Tuple[BlockHeader, ...]) -> int:
        return len(msg)


BaseGetNodeDataRequestManager = BaseRequestManager[
    'ETHPeer',
    NodeDataRequest,
    Tuple[bytes, ...],
    Tuple[Tuple[Hash32, bytes], ...],
]


class GetNodeDataRequestManager(BaseGetNodeDataRequestManager):
    msg_queue_maxsize = 100

    _response_msg_type: Type[Command] = NodeData

    async def __call__(self,  # type: ignore
                       node_hashes: Tuple[Hash32, ...],
                       timeout: int = None) -> Tuple[Tuple[Hash32, bytes], ...]:
        request = NodeDataRequest(node_hashes)
        return await self._request_and_wait(request, timeout)

    def _send_sub_proto_request(self, request: NodeDataRequest) -> None:
        self._peer.sub_proto.send_get_node_data(request)

    async def _normalize_response(self,
                                  msg: Tuple[bytes, ...]
                                  ) -> Tuple[Tuple[Hash32, bytes], ...]:
        if not isinstance(msg, tuple):
            raise MalformedMessage("Invalid msg, must be tuple of byte strings")
        elif not all(isinstance(item, bytes) for item in msg):
            raise MalformedMessage("Invalid msg, must be tuple of byte strings")

        node_keys = await self._run_in_executor(tuple, map(keccak, msg))
        return tuple(zip(node_keys, msg))

    def _get_item_count(self, msg: Tuple[bytes, ...]) -> int:
        return len(msg)
