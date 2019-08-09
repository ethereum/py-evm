from abc import abstractmethod
from typing import (
    Iterable,
    Tuple,
    TypeVar,
)

from eth_typing import (
    Hash32,
    BlockNumber,
)

from eth.abc import (
    BlockHeaderAPI,
)
from eth.db.header import HeaderDB

from trinity._utils.async_dispatch import async_method


TReturn = TypeVar('TReturn')


class BaseAsyncHeaderDB(HeaderDB):
    """
    Abstract base class for the async counterpart to ``HeaderDatabaseAPI``.
    """
    @abstractmethod
    async def coro_get_canonical_block_hash(self, block_number: BlockNumber) -> Hash32:
        ...

    @abstractmethod
    async def coro_get_canonical_block_header_by_number(self, block_number: BlockNumber) -> BlockHeaderAPI:  # noqa: E501
        ...

    @abstractmethod
    async def coro_get_canonical_head(self) -> BlockHeaderAPI:
        ...

    #
    # Header API
    #
    @abstractmethod
    async def coro_get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeaderAPI:
        ...

    @abstractmethod
    async def coro_get_score(self, block_hash: Hash32) -> int:
        ...

    @abstractmethod
    async def coro_header_exists(self, block_hash: Hash32) -> bool:
        ...

    @abstractmethod
    async def coro_persist_header(self, header: BlockHeaderAPI) -> Tuple[BlockHeaderAPI, ...]:
        ...

    @abstractmethod
    async def coro_persist_checkpoint_header(self, header: BlockHeaderAPI, score: int) -> None:
        ...

    @abstractmethod
    async def coro_persist_header_chain(
        self,
        headers: Iterable[BlockHeaderAPI],
        genesis_parent_hash: Hash32=None
    ) -> Tuple[BlockHeaderAPI, ...]:
        ...


class AsyncHeaderDB(BaseAsyncHeaderDB):
    coro_get_block_header_by_hash = async_method(BaseAsyncHeaderDB.get_block_header_by_hash)
    coro_get_canonical_block_hash = async_method(BaseAsyncHeaderDB.get_canonical_block_hash)
    coro_get_canonical_block_header_by_number = async_method(BaseAsyncHeaderDB.get_canonical_block_header_by_number)  # noqa: E501
    coro_get_canonical_head = async_method(BaseAsyncHeaderDB.get_canonical_head)
    coro_get_score = async_method(BaseAsyncHeaderDB.get_score)
    coro_header_exists = async_method(BaseAsyncHeaderDB.header_exists)
    coro_get_canonical_block_hash = async_method(BaseAsyncHeaderDB.get_canonical_block_hash)
    coro_persist_checkpoint_header = async_method(BaseAsyncHeaderDB.persist_checkpoint_header)
    coro_persist_header = async_method(BaseAsyncHeaderDB.persist_header)
    coro_persist_header_chain = async_method(BaseAsyncHeaderDB.persist_header_chain)
