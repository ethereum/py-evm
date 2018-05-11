from abc import abstractmethod
from pyting import Tuple

from evm.chains.header import BaseHeaderChain
from evm.rlp.headers import BlockHeader

from trinity.utils.mp import (
    async_method,
)


class BaseAsyncHeaderChain(BaseHeaderChain):
    @abstractmethod
    async def coro_get_canonical_head(self):
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    async def coro_import_header(self, header: BlockHeader) -> Tuple[BlockHeader, ...]:
        raise NotImplementedError("Chain classes must implement this method")


class AsyncHeaderChain(BaseAsyncHeaderChain):
    coro_get_canonical_head = async_method('get_canonical_head')
    coro_import_header = async_method('import_header')
