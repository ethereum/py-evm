from typing import (
    Any,
    Dict,
    Tuple,
)

from eth.rlp.headers import BlockHeader

from eth_utils import (
    ValidationError,
)

from trinity.protocol.common.validators import (
    BaseValidator,
    BaseBlockHeadersValidator,
)
from trinity.protocol.common.types import BlockBodyBundles

from . import constants


class GetBlockHeadersValidator(BaseBlockHeadersValidator):
    protocol_max_request_size = constants.MAX_HEADERS_FETCH


class GetBlockBodiesValidator(BaseValidator[BlockBodyBundles]):
    def __init__(self, headers: Tuple[BlockHeader, ...]) -> None:
        self.headers = headers

    def validate_result(self, response: BlockBodyBundles) -> None:
        expected_keys = {
            (header.transaction_root, header.uncles_hash)
            for header in self.headers
        }
        actual_keys = {
            (txn_root, uncles_hash)
            for body, (txn_root, trie_data), uncles_hash
            in response
        }
        unexpected_keys = actual_keys.difference(expected_keys)
        if unexpected_keys:
            raise ValidationError(f"Got {len(unexpected_keys)} unexpected block bodies")


def match_payload_request_id(request: Dict[str, Any], response: Dict[str, Any]) -> None:
    if request['request_id'] != response['request_id']:
        raise ValidationError("Request `id` does not match")
