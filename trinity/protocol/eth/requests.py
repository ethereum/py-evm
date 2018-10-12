from typing import (
    Any,
    Dict,
    Tuple,
)

from eth_typing import (
    BlockIdentifier,
    Hash32,
)
from p2p.protocol import BaseRequest

from trinity.protocol.eth.constants import MAX_HEADERS_FETCH
from trinity.protocol.common.requests import (
    BaseHeaderRequest,
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


class HeaderRequest(BaseHeaderRequest):
    """
    TODO: this should be removed from this module.  It exists to allow
    `trinity.protocol.eth.servers.PeerRequestHandler` to have a common API between light and
    full chains so maybe it should go there
    """
    max_size = MAX_HEADERS_FETCH

    def __init__(self,
                 block_number_or_hash: BlockIdentifier,
                 max_headers: int,
                 skip: int,
                 reverse: bool) -> None:
        self.block_number_or_hash = block_number_or_hash
        self.max_headers = max_headers
        self.skip = skip
        self.reverse = reverse


class GetBlockHeadersRequest(BaseRequest[Dict[str, Any]]):
    cmd_type = GetBlockHeaders
    response_type = BlockHeaders

    def __init__(self,
                 block_number_or_hash: BlockIdentifier,
                 max_headers: int,
                 skip: int,
                 reverse: bool) -> None:
        self.command_payload = {
            'block_number_or_hash': block_number_or_hash,
            'max_headers': max_headers,
            'skip': skip,
            'reverse': reverse
        }


class GetReceiptsRequest(BaseRequest[Tuple[Hash32, ...]]):
    cmd_type = GetReceipts
    response_type = Receipts

    def __init__(self, block_hashes: Tuple[Hash32, ...]) -> None:
        self.command_payload = block_hashes


class GetNodeDataRequest(BaseRequest[Tuple[Hash32, ...]]):
    cmd_type = GetNodeData
    response_type = NodeData

    def __init__(self, node_hashes: Tuple[Hash32, ...]) -> None:
        self.command_payload = node_hashes


class GetBlockBodiesRequest(BaseRequest[Tuple[Hash32, ...]]):
    cmd_type = GetBlockBodies
    response_type = BlockBodies

    def __init__(self, block_hashes: Tuple[Hash32, ...]) -> None:
        self.command_payload = block_hashes
