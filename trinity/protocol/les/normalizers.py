from typing import (
    Any,
    Dict,
    Tuple,
    TypeVar,
)

from eth.abc import BlockHeaderAPI

from p2p.exchange import BaseNormalizer

TResult = TypeVar('TResult')
BaseBlockHeadersNormalizer = BaseNormalizer[Dict[str, Any], Tuple[BlockHeaderAPI, ...]]


class BlockHeadersNormalizer(BaseBlockHeadersNormalizer):
    @staticmethod
    def normalize_result(message: Dict[str, Any]) -> Tuple[BlockHeaderAPI, ...]:
        result = message['headers']
        return result
