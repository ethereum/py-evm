import functools
from typing import (
    Tuple,
)

from eth_utils import to_tuple
from eth_utils.toolz import partition_all

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


@to_tuple
def _normalize_node_data(nodes):
    for node in nodes:
        yield keccak(node), node


class GetNodeDataNormalizer(BaseNormalizer[Tuple[bytes, ...], NodeDataBundles]):
    is_normalization_slow = True

    @staticmethod
    def normalize_result(msg: Tuple[bytes, ...]) -> NodeDataBundles:
        for nodes in partition_all(8, msg):
            yield functools.partial(_normalize_node_data, nodes)
        # node_keys = tuple(map(keccak, msg))
        # result = tuple(zip(node_keys, msg))
        # return result


@to_tuple
def _normalize_receipts(receipts_by_block):
    for receipts in receipts_by_block:
        yield receipts, make_trie_root_and_nodes(receipts)


class ReceiptsNormalizer(BaseNormalizer[ReceiptsByBlock, ReceiptsBundles]):
    is_normalization_slow = True

    @staticmethod
    def normalize_result(message: ReceiptsByBlock) -> ReceiptsBundles:
        for receipts_by_block in partition_all(8, message):
            yield functools.partial(_normalize_receipts, receipts_by_block)
        # trie_roots_and_data = tuple(map(make_trie_root_and_nodes, message))
        # return tuple(zip(message, trie_roots_and_data))


@to_tuple
def _normalize_block_bodies(bodies):
    for body in bodies:
        yield (
            body,
            make_trie_root_and_nodes(body.transactions),
            keccak(rlp.encode(body.uncles)),
        )


class GetBlockBodiesNormalizer(BaseNormalizer[Tuple[BlockBody, ...], BlockBodyBundles]):
    is_normalization_slow = True

    @staticmethod
    def normalize_result(msg: Tuple[BlockBody, ...]) -> BlockBodyBundles:
        for chunk in partition_all(8, msg):
            yield functools.partial(_normalize_block_bodies, chunk)
        # uncles_hashes = tuple(map(
        #     compose(keccak, rlp.encode),
        #     tuple(body.uncles for body in msg)
        # ))
        # transaction_roots_and_trie_data = tuple(map(
        #     make_trie_root_and_nodes,
        #     tuple(body.transactions for body in msg)
        # ))

        # body_bundles = tuple(zip(msg, transaction_roots_and_trie_data, uncles_hashes))
        # return body_bundles
