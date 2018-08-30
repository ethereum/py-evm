from typing import (
    Any,
    Dict,
    Tuple,
    TypeVar,
)

from eth.rlp.headers import BlockHeader

from trinity.protocol.common.normalizers import BaseNormalizer

TResult = TypeVar('TResult')
LESNormalizer = BaseNormalizer[Dict[str, Any], TResult]


class BlockHeadersNormalizer(LESNormalizer[Tuple[BlockHeader, ...]]):
    @staticmethod
    def normalize_result(message: Dict[str, Any]) -> Tuple[BlockHeader, ...]:
        result = message['headers']
        return result
