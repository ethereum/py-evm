from typing import (
    Dict,
    Tuple,
)

from eth_typing import (
    BlockIdentifier,
    Hash32,
)

from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt

from p2p.exceptions import ValidationError

from trinity.rlp.block_body import BlockBody
from trinity.protocol.common.requests import (
    BaseRequest,
    BaseHeaderRequest,
)

from . import constants


class HeaderRequest(BaseHeaderRequest[Tuple[BlockHeader, ...]]):
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


NodeDataBundles = Tuple[Tuple[Hash32, bytes], ...]


class NodeDataRequest(BaseRequest[Tuple[bytes, ...], NodeDataBundles]):
    def __init__(self, node_hashes: Tuple[Hash32, ...]) -> None:
        self.node_hashes = node_hashes

    def validate_response(self,
                          msg: Tuple[bytes, ...],
                          response: NodeDataBundles) -> None:
        if not response:
            # an empty response is always valid
            return

        node_keys = tuple(node_key for node_key, node in response)
        node_key_set = set(node_keys)

        if len(node_keys) != len(node_key_set):
            raise ValidationError("Response may not contain duplicate nodes")

        unexpected_keys = node_key_set.difference(self.node_hashes)

        if unexpected_keys:
            raise ValidationError(
                "Response contains {0} unexpected nodes".format(len(unexpected_keys))
            )


ReceiptsBundles = Tuple[Tuple[Tuple[Receipt, ...], Tuple[Hash32, Dict[Hash32, bytes]]], ...]
ReceiptsTuples = Tuple[Tuple[Receipt, ...], ...]


class ReceiptsRequest(BaseRequest[ReceiptsTuples, ReceiptsBundles]):
    def __init__(self, headers: Tuple[BlockHeader, ...]) -> None:
        self.headers = headers

    @property
    def block_hashes(self) -> Tuple[Hash32, ...]:
        return tuple(header.hash for header in self.headers)

    def validate_response(self,
                          msg: ReceiptsTuples,
                          response: ReceiptsBundles) -> None:
        if not response:
            # empty response is always valid.
            return

        expected_receipt_roots = set(header.receipt_root for header in self.headers)
        actual_receipt_roots = set(
            root_hash
            for receipt, (root_hash, trie_data)
            in response
        )

        unexpected_roots = actual_receipt_roots.difference(expected_receipt_roots)

        if unexpected_roots:
            raise ValidationError(
                "Got {0} unexpected receipt roots".format(len(unexpected_roots))
            )


# (BlockBody, (txn_root, txn_trie_data), uncles_hash)
BlockBodyBundles = Tuple[Tuple[
    BlockBody,
    Tuple[Hash32, Dict[Hash32, bytes]],
    Hash32,
], ...]
BodiesTuple = Tuple[BlockBody, ...]


class BlockBodiesRequest(BaseRequest[BodiesTuple, BlockBodyBundles]):
    def __init__(self, headers: Tuple[BlockHeader, ...]) -> None:
        self.headers = headers

    @property
    def block_hashes(self) -> Tuple[Hash32, ...]:
        return tuple(header.hash for header in self.headers)

    def validate_response(self,
                          msg: BodiesTuple,
                          response: BlockBodyBundles) -> None:
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
            raise ValidationError(
                "Got {0} unexpected block bodies".format(len(unexpected_keys))
            )
