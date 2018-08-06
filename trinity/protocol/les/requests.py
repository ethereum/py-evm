from typing import (
    Any,
    Dict,
    Tuple,
)

from eth_typing import BlockIdentifier

from eth.rlp.headers import BlockHeader

from p2p.exceptions import ValidationError

from trinity.protocol.common.requests import (
    BaseHeaderRequest,
)

from .constants import MAX_HEADERS_FETCH


HeadersResponseDict = Dict[str, Any]


class HeaderRequest(BaseHeaderRequest[HeadersResponseDict]):
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

    def validate_response(self,
                          msg: HeadersResponseDict,
                          response: Tuple[BlockHeader, ...]) -> None:
        if msg['request_id'] != self.request_id:
            raise ValidationError("Request `id` does not match")
        super().validate_response(msg, response)
