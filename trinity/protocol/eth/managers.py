from typing import (
    Dict,
    Tuple,
    Type,
    TYPE_CHECKING,
)

from cytoolz import concat

from eth_typing import (
    BlockIdentifier,
    Hash32,
)

from eth_hash.auto import keccak

from eth.db.trie import make_trie_root_and_nodes
from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt

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
    Receipts,
)
from .requests import (
    HeaderRequest,
    NodeDataRequest,
    ReceiptsRequest,
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
                                  msg: Tuple[BlockHeader, ...],
                                  ) -> Tuple[BlockHeader, ...]:
        return msg

    def _get_item_count(self, msg: Tuple[BlockHeader, ...]) -> int:
        return len(msg)


NodeDataBundles = Tuple[Tuple[Hash32, bytes], ...]
BaseGetNodeDataRequestManager = BaseRequestManager[
    'ETHPeer',
    NodeDataRequest,
    Tuple[bytes, ...],
    NodeDataBundles,
]


class GetNodeDataRequestManager(BaseGetNodeDataRequestManager):
    msg_queue_maxsize = 100

    _response_msg_type: Type[Command] = NodeData

    async def __call__(self,  # type: ignore
                       node_hashes: Tuple[Hash32, ...],
                       timeout: int = None) -> NodeDataBundles:
        request = NodeDataRequest(node_hashes)
        return await self._request_and_wait(request, timeout)

    def _send_sub_proto_request(self, request: NodeDataRequest) -> None:
        self._peer.sub_proto.send_get_node_data(request)

    async def _normalize_response(self,
                                  msg: Tuple[bytes, ...]
                                  ) -> NodeDataBundles:
        if not isinstance(msg, tuple):
            raise MalformedMessage("Invalid msg, must be tuple of byte strings")
        elif not all(isinstance(item, bytes) for item in msg):
            raise MalformedMessage("Invalid msg, must be tuple of byte strings")

        node_keys = await self._run_in_executor(tuple, map(keccak, msg))
        return tuple(zip(node_keys, msg))

    def _get_item_count(self, msg: Tuple[bytes, ...]) -> int:
        return len(msg)


ReceiptsBundles = Tuple[Tuple[Tuple[Receipt, ...], Tuple[Hash32, Dict[Hash32, bytes]]], ...]
ReceiptsByBlock = Tuple[Tuple[Receipt, ...], ...]
BaseGetReceiptsRequestManager = BaseRequestManager[
    'ETHPeer',
    ReceiptsRequest,
    ReceiptsByBlock,
    ReceiptsBundles,
]


class GetReceiptsRequestManager(BaseGetReceiptsRequestManager):
    msg_queue_maxsize = 100

    _response_msg_type: Type[Command] = Receipts

    async def __call__(self,  # type: ignore
                       headers: Tuple[BlockHeader, ...],
                       timeout: int = None) -> ReceiptsBundles:
        request = ReceiptsRequest(headers)
        return await self._request_and_wait(request, timeout)

    def _send_sub_proto_request(self, request: ReceiptsRequest) -> None:
        self._peer.sub_proto.send_get_receipts(request)

    async def _normalize_response(self,
                                  response: Tuple[Tuple[Receipt, ...], ...],
                                  ) -> ReceiptsBundles:
        if not isinstance(response, tuple):
            raise MalformedMessage(
                "`GetReceipts` response must be a tuple. Got: {0}".format(type(response))
            )
        elif not all(isinstance(item, tuple) for item in response):
            raise MalformedMessage("`GetReceipts` response must be a tuple of tuples")

        for item in response:
            if not all(isinstance(value, Receipt) for value in item):
                raise MalformedMessage(
                    "Response must be a tuple of tuples of `BlockHeader` objects"
                )

        trie_roots_and_data = await self._run_in_executor(
            tuple,
            map(make_trie_root_and_nodes, response),
        )
        receipt_bundles = tuple(zip(response, trie_roots_and_data))
        return receipt_bundles

    def _get_item_count(self, msg: ReceiptsByBlock) -> int:
        return len(concat(msg))
