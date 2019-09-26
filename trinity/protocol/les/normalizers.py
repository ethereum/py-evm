from typing import (
    Tuple,
    TypeVar,
)

from eth.abc import BlockHeaderAPI

from p2p.exchange import BaseNormalizer

from .commands import BlockHeaders

TResult = TypeVar('TResult')
BaseBlockHeadersNormalizer = BaseNormalizer[BlockHeaders, Tuple[BlockHeaderAPI, ...]]


class BlockHeadersNormalizer(BaseBlockHeadersNormalizer):
    @staticmethod
    def normalize_result(cmd: BlockHeaders) -> Tuple[BlockHeaderAPI, ...]:
        return cmd.payload.headers
