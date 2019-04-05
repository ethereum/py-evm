from typing import (
    Iterable,
    Tuple,
)

from eth_utils import (
    to_tuple,
)
from eth.db.trie import make_trie_root_and_nodes
from eth_hash.auto import keccak
import rlp

from trinity.protocol.common.normalizers import (
    BaseNormalizer,
)
from trinity.protocol.common.types import (
    BlockBodyBundle,
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
        node_keys = map(keccak, msg)
        result = tuple(zip(node_keys, msg))
        return result


class ReceiptsNormalizer(BaseNormalizer[ReceiptsByBlock, ReceiptsBundles]):
    is_normalization_slow = True

    @staticmethod
    def normalize_result(message: ReceiptsByBlock) -> ReceiptsBundles:
        trie_roots_and_data = map(make_trie_root_and_nodes, message)
        return tuple(zip(message, trie_roots_and_data))


class GetBlockBodiesNormalizer(BaseNormalizer[Tuple[BlockBody, ...], BlockBodyBundles]):
    is_normalization_slow = True

    @staticmethod
    @to_tuple
    def normalize_result(msg: Tuple[BlockBody, ...]) -> Iterable[BlockBodyBundle]:
        for body in msg:
            uncle_hashes = keccak(rlp.encode(body.uncles))
            transaction_root_and_nodes = make_trie_root_and_nodes(body.transactions)
            yield body, transaction_root_and_nodes, uncle_hashes
