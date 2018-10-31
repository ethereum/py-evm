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

from trinity.protocol.common.requests import (
    BaseHeaderRequest,
)

from trinity.protocol.les.constants import MAX_HEADERS_FETCH
from .commands import (
    BlockHeaders,
    GetBlockHeaders,
    GetBlockHeadersQuery,
    BlockBodies,
    GetBlockBodies,
)


HeadersResponseDict = Dict[str, Any]


class HeaderRequest(BaseHeaderRequest):
    request_id: int

    max_size = MAX_HEADERS_FETCH

    def __init__(self,
                 block_number_or_hash: BlockIdentifier,
                 max_headers: int,
                 skip: int,
                 reverse: bool,
                 request_id: int) -> None:
        self.block_number_or_hash = block_number_or_hash
        self.max_headers = max_headers
        self.skip = skip
        self.reverse = reverse
        self.request_id = request_id

LESRequest = BaseRequest[Dict[str, Any]]

class GetBlockHeadersRequest(LESRequest):
    cmd_type = GetBlockHeaders
    response_type = BlockHeaders

    def __init__(self,
                 block_number_or_hash: BlockIdentifier,
                 max_headers: int,
                 skip: int,
                 reverse: bool,
                 request_id: int) -> None:
        self.command_payload = {
            'request_id': request_id,
            'query': GetBlockHeadersQuery(
                block_number_or_hash,
                max_headers,
                skip,
                reverse,
            ),
        }


class GetBlockBodiesRequest(LESRequest):
    cmd_type = GetBlockBodies
    response_type = BlockBodies

    def __init__(self,
                 block_hashes: Tuple[Hash32, ...],
                 request_id: int) -> None:
        self.command_payload = {
            'request_id': request_id,
            'block_hashes': block_hashes,
        }
