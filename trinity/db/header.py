from abc import abstractmethod
# Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
# https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
from multiprocessing.managers import (  # type: ignore
    BaseProxy,
)
from typing import Tuple

from eth_typing import (
    Hash32,
    BlockNumber,
)

from evm.db.header import (
    BaseHeaderDB,
    HeaderDB,
)
from evm.rlp.headers import BlockHeader

from trinity.utils.mp import (
    async_method,
    sync_method,
)


class BaseAsyncHeaderDB(BaseHeaderDB):
    #
    # Canonical Chain API
    #
    @abstractmethod
    async def coro_get_canonical_block_hash(self, block_number: BlockNumber) -> Hash32:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    async def coro_get_canonical_block_header_by_number(self, block_number: BlockNumber) -> BlockHeader:  # noqa: E501
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    async def coro_get_canonical_head(self) -> BlockHeader:
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Header API
    #
    @abstractmethod
    async def coro_get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    async def coro_get_score(self, block_hash: Hash32) -> int:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    async def coro_header_exists(self, block_hash: Hash32) -> bool:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    async def coro_persist_header(self, header: BlockHeader) -> Tuple[BlockHeader, ...]:
        raise NotImplementedError("ChainDB classes must implement this method")


class AsyncHeaderDB(HeaderDB, BaseAsyncHeaderDB):
    async def coro_get_canonical_block_hash(self, block_number: BlockNumber) -> Hash32:
        raise NotImplementedError("ChainDB classes must implement this method")

    async def coro_get_canonical_block_header_by_number(self, block_number: BlockNumber) -> BlockHeader:  # noqa: E501
        raise NotImplementedError("ChainDB classes must implement this method")

    async def coro_get_canonical_head(self) -> BlockHeader:
        raise NotImplementedError("ChainDB classes must implement this method")

    async def coro_get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeader:
        raise NotImplementedError("ChainDB classes must implement this method")

    async def coro_get_score(self, block_hash: Hash32) -> int:
        raise NotImplementedError("ChainDB classes must implement this method")

    async def coro_header_exists(self, block_hash: Hash32) -> bool:
        raise NotImplementedError("ChainDB classes must implement this method")

    async def coro_persist_header(self, header: BlockHeader) -> Tuple[BlockHeader, ...]:
        raise NotImplementedError("ChainDB classes must implement this method")


class AsyncHeaderDBProxy(BaseProxy, BaseAsyncHeaderDB, BaseHeaderDB):
    coro_get_block_header_by_hash = async_method('get_block_header_by_hash')
    coro_get_canonical_block_hash = async_method('get_canonical_block_hash')
    coro_get_canonical_block_header_by_number = async_method('get_canonical_block_header_by_number')
    coro_get_canonical_head = async_method('get_canonical_head')
    coro_get_score = async_method('get_score')
    coro_header_exists = async_method('header_exists')
    coro_get_canonical_block_hash = async_method('get_canonical_block_hash')
    coro_persist_header = async_method('persist_header')

    get_block_header_by_hash = sync_method('get_block_header_by_hash')
    get_canonical_block_hash = sync_method('get_canonical_block_hash')
    get_canonical_block_header_by_number = sync_method('get_canonical_block_header_by_number')
    get_canonical_head = sync_method('get_canonical_head')
    get_score = sync_method('get_score')
    header_exists = sync_method('header_exists')
    get_canonical_block_hash = sync_method('get_canonical_block_hash')
    persist_header = sync_method('persist_header')
