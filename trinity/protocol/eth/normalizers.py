from typing import (
    Tuple,
)

from cytoolz import (
    compose,
)
from eth.db.trie import make_trie_root_and_nodes
from eth_hash.auto import keccak
import rlp

from trinity.protocol.common.normalizers import (
    BaseNormalizer,
)
from trinity.protocol.common.types import (
    BlockBodyBundles,
    NodeDataBundles,
    ReceiptsBundles,
    ReceiptsByBlock,
)
from trinity.rlp.block_body import BlockBody


class GetNodeDataNormalizer(BaseNormalizer[Tuple[bytes, ...], NodeDataBundles]):
    is_normalization_slow = True

    @staticmethod
    def normalize_result(msg: Tuple[bytes, ...]) -> NodeDataBundles:
        node_keys = tuple(map(keccak, msg))
        result = tuple(zip(node_keys, msg))
        return result


class ReceiptsNormalizer(BaseNormalizer[ReceiptsByBlock, ReceiptsBundles]):
    is_normalization_slow = True

    @staticmethod
    def normalize_result(message: ReceiptsByBlock) -> ReceiptsBundles:
        trie_roots_and_data = tuple(map(make_trie_root_and_nodes, message))
        return tuple(zip(message, trie_roots_and_data))


class GetBlockBodiesNormalizer(BaseNormalizer[Tuple[BlockBody, ...], BlockBodyBundles]):
    is_normalization_slow = True

    @staticmethod
    def normalize_result(msg: Tuple[BlockBody, ...]) -> BlockBodyBundles:
        uncles_hashes = tuple(map(
            compose(keccak, rlp.encode),
            tuple(body.uncles for body in msg)
        ))
        transaction_roots_and_trie_data = tuple(map(
            make_trie_root_and_nodes,
            tuple(body.transactions for body in msg)
        ))

        body_bundles = tuple(zip(msg, transaction_roots_and_trie_data, uncles_hashes))
        return body_bundles
