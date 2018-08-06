from typing import (
    Any,
    cast,
    Tuple,
)

from eth_typing import BlockIdentifier

from eth.rlp.headers import BlockHeader

from p2p.exceptions import ValidationError

from trinity.protocol.common.requests import BaseHeaderRequest

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

    def validate_response(self, response: Any) -> None:
        """
        Core `Request` API used for validation.
        """
        if not isinstance(response, dict):
            raise ValidationError("Response to `HeaderRequest` must be a dict")

        request_id = response['request_id']
        if request_id != self.request_id:
            raise ValidationError(
                "Response `request_id` does not match.  expected: %s | got: %s".format(
                    self.request_id,
                    request_id,
                )
            )
        elif not all(isinstance(item, BlockHeader) for item in response['headers']):
            raise ValidationError("Response must be a tuple of `BlockHeader` objects")

        return self.validate_headers(cast(Tuple[BlockHeader, ...], response['headers']))
