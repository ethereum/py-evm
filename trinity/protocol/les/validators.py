from typing import (
    Any,
    Dict,
    Tuple)

from eth_utils import (
    ValidationError,
)

from eth.rlp.headers import BlockHeader
from trinity.protocol.common.types import ReceiptsBundles
from trinity.protocol.common.validators import (
    BaseBlockHeadersValidator,
    BaseValidator)
from . import constants


class GetBlockHeadersValidator(BaseBlockHeadersValidator):
    protocol_max_request_size = constants.MAX_HEADERS_FETCH


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


def match_payload_request_id(request: Dict[str, Any], response: Dict[str, Any]) -> None:
    if request['request_id'] != response['request_id']:
        raise ValidationError("Request `id` does not match")
