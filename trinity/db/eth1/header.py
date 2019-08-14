from abc import (
    ABC,
    abstractmethod,
)
# Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
# https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
from multiprocessing.managers import (  # type: ignore
    BaseProxy,
)
from typing import (
    Iterable,
    Tuple,
)

from eth_typing import (
    Hash32,
    BlockNumber,
)

from eth.abc import (
    AtomicDatabaseAPI,
    BlockHeaderAPI,
)

from trinity._utils.mp import (
    async_method,
)


class BaseAsyncHeaderDB(ABC):
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
    async def coro_persist_header_chain(self,
                                        headers: Iterable[BlockHeaderAPI],
                                        ) -> Tuple[BlockHeaderAPI, ...]:
        ...


class AsyncHeaderDBPreProxy(BaseAsyncHeaderDB):
    """
    Proxy implementation of ``BaseAsyncHeaderDB`` that does not derive from
    ``BaseProxy`` for the purpose of improved testability.
    """

    def __init__(self, db: AtomicDatabaseAPI) -> None:
        pass

    coro_get_block_header_by_hash = async_method('get_block_header_by_hash')
    coro_get_canonical_block_hash = async_method('get_canonical_block_hash')
    coro_get_canonical_block_header_by_number = async_method('get_canonical_block_header_by_number')
    coro_get_canonical_head = async_method('get_canonical_head')
    coro_get_score = async_method('get_score')
    coro_header_exists = async_method('header_exists')
    coro_get_canonical_block_hash = async_method('get_canonical_block_hash')
    coro_persist_header = async_method('persist_header')
    coro_persist_header_chain = async_method('persist_header_chain')


class AsyncHeaderDBProxy(BaseProxy, AsyncHeaderDBPreProxy):
    """
    Turn ``AsyncHeaderDBPreProxy`` into an actual proxy by deriving from ``BaseProxy``
    """
    pass
