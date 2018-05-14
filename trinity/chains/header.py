from abc import abstractmethod
# Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
# https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
from multiprocessing.managers import (  # type: ignore
    BaseProxy,
)
from typing import Tuple, Type

from evm.db.backends.base import BaseDB
from evm.chains.header import (
    BaseHeaderChain,
    HeaderChain,
)
from evm.rlp.headers import BlockHeader

from trinity.db.header import (
    AsyncHeaderDB,
    BaseAsyncHeaderDB,
)
from trinity.utils.mp import (
    async_method,
    sync_method,
)


class BaseAsyncHeaderChain(BaseHeaderChain):
    @abstractmethod
    async def coro_get_canonical_head(self):
        raise NotImplementedError("Chain classes must implement this method")

    @abstractmethod
    async def coro_import_header(self, header: BlockHeader) -> Tuple[BlockHeader, ...]:
        raise NotImplementedError("Chain classes must implement this method")


class AsyncHeaderChain(HeaderChain, BaseAsyncHeaderChain):
    _headerdb_class: Type[BaseAsyncHeaderDB] = AsyncHeaderDB

    async def coro_get_canonical_head(self):
        raise NotImplementedError("Chain classes must implement this method")

    async def coro_import_header(self, header: BlockHeader) -> Tuple[BlockHeader, ...]:
        raise NotImplementedError("Chain classes must implement this method")


class AsyncHeaderChainProxy(BaseProxy, BaseAsyncHeaderChain, BaseHeaderChain):
    @classmethod
    def from_genesis_header(cls,
                            basedb: BaseDB,
                            genesis_header: BlockHeader) -> 'BaseHeaderChain':
        raise NotImplementedError("Chain classes must implement this method")

    @classmethod
    def get_headerdb_class(cls):
        raise NotImplementedError("Chain classes must implement this method")

    coro_get_block_header_by_hash = async_method('get_block_header_by_hash')
    coro_get_canonical_block_header_by_number = async_method('get_canonical_block_header_by_number')
    coro_get_canonical_head = async_method('get_canonical_head')
    coro_import_header = async_method('import_header')
    coro_header_exists = async_method('header_exists')

    get_block_header_by_hash = sync_method('get_block_header_by_hash')
    get_canonical_block_header_by_number = sync_method('get_canonical_block_header_by_number')
    get_canonical_head = sync_method('get_canonical_head')
    import_header = sync_method('import_header')
    header_exists = sync_method('header_exists')
