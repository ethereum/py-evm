from abc import abstractmethod
from typing import Tuple

from eth.abc import (
    BlockHeaderAPI,
    HeaderChainAPI,
)
from eth.chains.header import (
    HeaderChain,
)


class BaseAsyncHeaderChain(HeaderChainAPI):
    @abstractmethod
    async def coro_get_canonical_head(self) -> BlockHeaderAPI:
        ...

    @abstractmethod
    async def coro_import_header(self, header: BlockHeaderAPI) -> Tuple[BlockHeaderAPI, ...]:
        ...


class AsyncHeaderChain(HeaderChain, BaseAsyncHeaderChain):

    async def coro_get_canonical_head(self) -> BlockHeaderAPI:
        raise NotImplementedError("Chain classes must implement this method")

    async def coro_import_header(self, header: BlockHeaderAPI) -> Tuple[BlockHeaderAPI, ...]:
        raise NotImplementedError("Chain classes must implement this method")
