from eth_typing import BlockIdentifier


from trinity.protocol.common.requests import (
    BaseHeaderRequest,
)

from .constants import MAX_HEADERS_FETCH


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
