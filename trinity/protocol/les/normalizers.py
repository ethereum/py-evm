from typing import (
    Any,
    Dict,
    Tuple,
    TypeVar,
)

from eth_utils import keccak

from eth.rlp.headers import BlockHeader

from trinity.protocol.common.normalizers import BaseNormalizer
from trinity.protocol.common.types import NodeDataBundles

TResult = TypeVar('TResult')
LESNormalizer = BaseNormalizer[Dict[str, Any], TResult]


class BlockHeadersNormalizer(LESNormalizer[Tuple[BlockHeader, ...]]):
    @staticmethod
    def normalize_result(message: Dict[str, Any]) -> Tuple[BlockHeader, ...]:
        result = message['headers']
        return result



class GetNodeDataNormalizer(LESNormalizer[NodeDataBundles]):
    is_normalization_slow = True

    @staticmethod
    def normalize_result(msg: Dict[str, Any]) -> NodeDataBundles:
        node_keys = tuple(map(keccak, msg))
        result = tuple(zip(node_keys, msg))
        return result
