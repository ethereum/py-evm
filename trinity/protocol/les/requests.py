from typing import (
    Any,
    Dict,
)

from eth_typing import BlockIdentifier

from p2p.protocol import BaseRequest

from trinity.protocol.common.requests import (
    BaseHeaderRequest,
)

from trinity.protocol.les.constants import MAX_HEADERS_FETCH
from .commands import (
    BlockHeaders,
    GetBlockHeaders,
    GetBlockHeadersQuery,
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


class GetBlockHeadersRequest(BaseRequest[Dict[str, Any]]):
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
