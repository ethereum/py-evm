from typing import (
    Tuple,
)

from eth_typing import (
    BlockIdentifier,
    Hash32,
)

from p2p.exceptions import ValidationError

from trinity.protocol.common.requests import (
    BaseRequest,
    BaseHeaderRequest,
)

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


class NodeDataRequest(BaseRequest):
    node_keys_cache: Tuple[Hash32, ...]

    def __init__(self, node_hashes: Tuple[Hash32, ...]) -> None:
        self.node_hashes = node_hashes

    def validate_response(self, response: Tuple[Tuple[Hash32, bytes], ...]) -> None:
        """
        Core `Request` API used for validation.
        """
        return self.validate_node_data(response)

    def validate_node_data(self, node_data: Tuple[Tuple[Hash32, bytes], ...]) -> None:
        if not node_data:
            # an empty response is always valid
            return

        node_keys = tuple(node_key for node_key, node in node_data)
        node_key_set = set(node_keys)

        if len(node_keys) != len(node_key_set):
            raise ValidationError("Response may not contain duplicate nodes")

        unexpected_keys = node_key_set.difference(self.node_hashes)

        if unexpected_keys:
            raise ValidationError(
                "Response contains {0} unexpected nodes".format(len(unexpected_keys))
            )
