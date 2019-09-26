from typing import (
    Iterable,
    Tuple,
)

from eth_utils import (
    to_tuple,
)
from eth.abc import BlockHeaderAPI
from eth.db.trie import make_trie_root_and_nodes
from eth_hash.auto import keccak
import rlp

from p2p.exchange import BaseNormalizer

from trinity.protocol.common.typing import (
    BlockBodyBundle,
    BlockBodyBundles,
    NodeDataBundles,
    ReceiptsBundles,
)

from .commands import (
    BlockHeaders,
    BlockBodies,
    NodeData,
    Receipts,
)


BaseBlockHeadersNormalizer = BaseNormalizer[BlockHeaders, Tuple[BlockHeaderAPI, ...]]


class BlockHeadersNormalizer(BaseBlockHeadersNormalizer):
    @staticmethod
    def normalize_result(cmd: BlockHeaders) -> Tuple[BlockHeaderAPI, ...]:
        return cmd.payload


class GetNodeDataNormalizer(BaseNormalizer[NodeData, NodeDataBundles]):
    is_normalization_slow = True

    @staticmethod
    def normalize_result(cmd: NodeData) -> NodeDataBundles:
        node_keys = map(keccak, cmd.payload)
        result = tuple(zip(node_keys, cmd.payload))
        return result


class ReceiptsNormalizer(BaseNormalizer[Receipts, ReceiptsBundles]):
    is_normalization_slow = True

    @staticmethod
    def normalize_result(cmd: Receipts) -> ReceiptsBundles:
        trie_roots_and_data = map(make_trie_root_and_nodes, cmd.payload)
        return tuple(zip(cmd.payload, trie_roots_and_data))


class GetBlockBodiesNormalizer(BaseNormalizer[BlockBodies, BlockBodyBundles]):
    is_normalization_slow = True

    @staticmethod
    @to_tuple
    def normalize_result(cmd: BlockBodies) -> Iterable[BlockBodyBundle]:
        for body in cmd.payload:
            uncle_hashes = keccak(rlp.encode(body.uncles))
            transaction_root_and_nodes = make_trie_root_and_nodes(body.transactions)
            yield body, transaction_root_and_nodes, uncle_hashes
