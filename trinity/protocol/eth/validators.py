from typing import (
    Tuple,
)

from eth.rlp.headers import BlockHeader
from eth_typing import (
    Hash32,
)
from eth_utils import (
    ValidationError,
)

from trinity.protocol.common.validators import (
    BaseValidator,
    BaseBlockHeadersValidator,
)
from trinity.protocol.common.types import (
    BlockBodyBundles,
    NodeDataBundles,
    ReceiptsBundles,
)

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


class ReceiptsValidator(BaseValidator[ReceiptsBundles]):
    def __init__(self, headers: Tuple[BlockHeader, ...]) -> None:
        self.headers = headers

    def validate_result(self, result: ReceiptsBundles) -> None:
        if not result:
            # empty result is always valid.
            return

        expected_receipt_roots = set(header.receipt_root for header in self.headers)
        actual_receipt_roots = set(
            root_hash
            for receipt, (root_hash, trie_data)
            in result
        )

        unexpected_roots = actual_receipt_roots.difference(expected_receipt_roots)

        if unexpected_roots:
            raise ValidationError(f"Got {len(unexpected_roots)} unexpected receipt roots")


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
