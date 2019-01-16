from abc import abstractmethod
from typing import Tuple

from eth.chains.header import (
    BaseHeaderChain,
    HeaderChain,
)
from eth.rlp.headers import BlockHeader


class BaseAsyncHeaderChain(BaseHeaderChain):
    @abstractmethod
    async def coro_get_canonical_head(self) -> BlockHeader:
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    async def coro_import_header(self, header: BlockHeader) -> Tuple[BlockHeader, ...]:
        raise NotImplementedError("Chain classes must implement this method")


class AsyncHeaderChain(HeaderChain, BaseAsyncHeaderChain):

    async def coro_get_canonical_head(self) -> BlockHeader:
        raise NotImplementedError("Chain classes must implement this method")

    async def coro_import_header(self, header: BlockHeader) -> Tuple[BlockHeader, ...]:
        raise NotImplementedError("Chain classes must implement this method")
