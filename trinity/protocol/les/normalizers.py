from typing import (
    Any,
    Dict,
    Tuple,
    TypeVar,
)

from eth.rlp.headers import BlockHeader

from trinity.protocol.common.normalizers import BaseNormalizer
from trinity.protocol.common.types import BlockBodyBundles


TResult = TypeVar('TResult')
LESNormalizer = BaseNormalizer[Dict[str, Any], TResult]


class BlockHeadersNormalizer(LESNormalizer[Tuple[BlockHeader, ...]]):
    @staticmethod
    def normalize_result(message: Dict[str, Any]) -> Tuple[BlockHeader, ...]:
        result = message['headers']
        return result


class GetBlockBodiesNormalizer(LESNormalizer[BlockBodyBundles]):
    @staticmethod
    def normalize_result(message: Dict[str, Any]) -> BlockBodyBundles:
        bodies = message['bodies']

        uncles_hashes = tuple(map(
            compose(keccak, rlp.encode),
            tuple(body.uncles for body in bodies)
        ))
        transaction_roots_and_trie_data = tuple(map(
            make_trie_root_and_nodes,
            tuple(body.transactions for body in bodies)
        ))

        body_bundles = tuple(zip(bodies, transaction_roots_and_trie_data, uncles_hashes))
        return body_bundles
