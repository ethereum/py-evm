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
from eth.db.chain import BaseChainDB
from eth.rlp.blocks import BaseBlock
from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt
from eth.rlp.transactions import BaseTransaction

from trinity._utils.mp import (
    async_method,
    sync_method,
)


class BaseAsyncChainDB(BaseChainDB):
    """
    Abstract base class extends the abstract ``BaseChainDB`` with async APIs.
    """

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

    coro_get = async_method('get')
    coro_get_block_header_by_hash = async_method('get_block_header_by_hash')
    coro_get_canonical_head = async_method('get_canonical_head')
    coro_get_score = async_method('get_score')
    coro_header_exists = async_method('header_exists')
    coro_get_canonical_block_hash = async_method('get_canonical_block_hash')
    coro_get_canonical_block_header_by_number = async_method('get_canonical_block_header_by_number')
    coro_persist_header = async_method('persist_header')
    coro_persist_block = async_method('persist_block')
    coro_persist_uncles = async_method('persist_uncles')
    coro_persist_trie_data_dict = async_method('persist_trie_data_dict')
    coro_get_block_transactions = async_method('get_block_transactions')
    coro_get_block_uncles = async_method('get_block_uncles')
    coro_get_receipts = async_method('get_receipts')

    add_receipt = sync_method('add_receipt')
    add_transaction = sync_method('add_transaction')
    exists = sync_method('exists')
    get = sync_method('get')
    get_block_header_by_hash = sync_method('get_block_header_by_hash')
    get_block_transactions = sync_method('get_block_transactions')
    get_block_transaction_hashes = sync_method('get_block_transaction_hashes')
    get_block_uncles = sync_method('get_block_uncles')
    get_canonical_head = sync_method('get_canonical_head')
    get_receipts = sync_method('get_receipts')
    get_score = sync_method('get_score')
    get_transaction_by_index = sync_method('get_transaction_by_index')
    get_transaction_index = sync_method('get_transaction_index')
    header_exists = sync_method('header_exists')
    get_canonical_block_header_by_number = sync_method('get_canonical_block_header_by_number')
    get_canonical_block_hash = sync_method('get_canonical_block_hash')
    persist_block = sync_method('persist_block')
    persist_header = sync_method('persist_header')
    persist_header_chain = sync_method('persist_header_chain')
    persist_uncles = sync_method('persist_uncles')
    persist_trie_data_dict = sync_method('persist_trie_data_dict')


class AsyncChainDBProxy(BaseProxy, AsyncChainDBPreProxy):
    """
    Turn ``AsyncChainDBPreProxy`` into an actual proxy by deriving from ``BaseProxy``
    """
    pass
