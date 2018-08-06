from typing import (
    Any,
    cast,
    Tuple,
)

from eth_typing import BlockIdentifier

from eth.rlp.headers import BlockHeader

from p2p.exceptions import ValidationError

from trinity.protocol.common.requests import BaseHeaderRequest

from . import constants


class HeaderRequest(BaseHeaderRequest):
    @property
    def max_size(self) -> int:
        return constants.MAX_HEADERS_FETCH

    def __init__(self,
                 block_number_or_hash: BlockIdentifier,
                 max_headers: int,
                 skip: int,
                 reverse: bool) -> None:
        self.block_number_or_hash = block_number_or_hash
        self.max_headers = max_headers
        self.skip = skip
        self.reverse = reverse

    def validate_response(self, response: Any) -> None:
        """
        Core `Request` API used for validation.
        """
        if not isinstance(response, tuple):
            raise ValidationError("Response to `HeaderRequest` must be a tuple")
        elif not all(isinstance(item, BlockHeader) for item in response):
            raise ValidationError("Response must be a tuple of `BlockHeader` objects")

        return self.validate_headers(cast(Tuple[BlockHeader, ...], response))
