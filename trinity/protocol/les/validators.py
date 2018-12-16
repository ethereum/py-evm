from typing import (
    Any,
    Dict,
    Tuple)

from eth_typing import Hash32
from eth_utils import (
    ValidationError,
)

from trinity.protocol.common.types import NodeDataBundles
from trinity.protocol.common.validators import (
    BaseBlockHeadersValidator,
    BaseValidator)
from . import constants


class GetBlockHeadersValidator(BaseBlockHeadersValidator):
    protocol_max_request_size = constants.MAX_HEADERS_FETCH


class GetNodeDataValidator(BaseValidator[NodeDataBundles]):
    def __init__(self, node_hashes: Tuple[Hash32, ...]) -> None:
        self.node_hashes = node_hashes

    def validate_result(self, response: NodeDataBundles) -> None:
        if not response:
            # an empty response is always valid
            return

        node_keys = tuple(node_key for node_key, node in response)
        node_key_set = set(node_keys)

        if len(node_keys) != len(node_key_set):
            raise ValidationError("Response may not contain duplicate nodes")

        unexpected_keys = node_key_set.difference(self.node_hashes)

        if unexpected_keys:
            raise ValidationError(f"Response contains {len(unexpected_keys)} unexpected nodes")


def match_payload_request_id(request: Dict[str, Any], response: Dict[str, Any]) -> None:
    if request['request_id'] != response['request_id']:
        raise ValidationError("Request `id` does not match")
