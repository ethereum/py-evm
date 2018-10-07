from typing import (
    Any,
    Dict,
    Tuple,
    TypeVar,
)

from eth.rlp.headers import BlockHeader

from trinity.protocol.common.normalizers import BaseNormalizer
from trinity.rlp.block_body import BlockBody

TResult = TypeVar('TResult')
LESNormalizer = BaseNormalizer[Dict[str, Any], TResult]


# Q: Shouldn't this be named GetBlockHeadersNormalizer?
class BlockHeadersNormalizer(LESNormalizer[Tuple[BlockHeader, ...]]):
    @staticmethod
    def normalize_result(message: Dict[str, Any]) -> Tuple[BlockHeader, ...]:
        result = message['headers']
        return result


class GetBlockBodiesNormalizer(LESNormalizer[Tuple[BlockBody, ...]]):
    @staticmethod
    def normalize_result(message: Dict[str, Any]) -> Tuple[BlockBody, ...]:
        result = message['bodies']
        return result
