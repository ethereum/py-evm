from abc import abstractmethod
# Typeshed definitions for multiprocessing.managers is incomplete, so ignore them for now:
# https://github.com/python/typeshed/blob/85a788dbcaa5e9e9a62e55f15d44530cd28ba830/stdlib/3/multiprocessing/managers.pyi#L3
from multiprocessing.managers import (  # type: ignore
    BaseProxy,
)
from typing import (
    Dict,
    Iterable,
    List,
    Tuple,
    Type,
)

from eth_typing import Hash32

from eth.db.backends.base import BaseAtomicDB
from eth.rlp.blocks import BaseBlock
from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt
from eth.rlp.transactions import BaseTransaction

from trinity.db.eth1.header import BaseAsyncHeaderDB
from trinity._utils.mp import (
    async_method,
)


class BaseAsyncChainDB(BaseAsyncHeaderDB):
    """
    Abstract base class for the async counterpart to ``BaseChainDB``.
    """

    @abstractmethod
    async def coro_exists(self, key: bytes) -> bool:
        pass

    @abstractmethod
    async def coro_get(self, key: bytes) -> bytes:
        pass

    @abstractmethod
    async def coro_persist_block(self, block: BaseBlock) -> None:
        pass

    @abstractmethod
    async def coro_persist_uncles(self, uncles: Tuple[BlockHeader]) -> Hash32:
        pass

    @abstractmethod
    async def coro_persist_trie_data_dict(self, trie_data_dict: Dict[Hash32, bytes]) -> None:
        pass

    @abstractmethod
    async def coro_get_block_transactions(
            self,
            header: BlockHeader,
            transaction_class: Type[BaseTransaction]) -> Iterable[BaseTransaction]:
        pass

    @abstractmethod
    async def coro_get_block_uncles(self, uncles_hash: Hash32) -> List[BlockHeader]:
        pass

    @abstractmethod
    async def coro_get_receipts(
            self, header: BlockHeader, receipt_class: Type[Receipt]) -> List[Receipt]:
        pass


class AsyncChainDBPreProxy(BaseAsyncChainDB):
    """
    Proxy implementation of ``BaseAsyncChainDB`` that does not derive from
    ``BaseProxy`` for the purpose of improved testability.
    """

    def __init__(self, db: BaseAtomicDB) -> None:
        pass

    coro_exists = async_method('exists')
    coro_get = async_method('get')
    coro_get_block_header_by_hash = async_method('get_block_header_by_hash')
    coro_get_canonical_head = async_method('get_canonical_head')
    coro_get_score = async_method('get_score')
    coro_header_exists = async_method('header_exists')
    coro_get_canonical_block_hash = async_method('get_canonical_block_hash')
    coro_get_canonical_block_header_by_number = async_method('get_canonical_block_header_by_number')
    coro_persist_header = async_method('persist_header')
    coro_persist_header_chain = async_method('persist_header_chain')
    coro_persist_block = async_method('persist_block')
    coro_persist_header_chain = async_method('persist_header_chain')
    coro_persist_uncles = async_method('persist_uncles')
    coro_persist_trie_data_dict = async_method('persist_trie_data_dict')
    coro_get_block_transactions = async_method('get_block_transactions')
    coro_get_block_uncles = async_method('get_block_uncles')
    coro_get_receipts = async_method('get_receipts')


class AsyncChainDBProxy(BaseProxy, AsyncChainDBPreProxy):
    """
    Turn ``AsyncChainDBPreProxy`` into an actual proxy by deriving from ``BaseProxy``
    """
    pass
