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
    TYPE_CHECKING,
)

from eth_typing import (
    BlockNumber,
    Hash32,
)

from evm.db.chain import (
    BaseChainDB,
    ChainDB,
)
from evm.rlp.headers import BlockHeader
from evm.rlp.receipts import Receipt

from trinity.utils.mp import (
    async_method,
    sync_method,
)

if TYPE_CHECKING:
    from evm.rlp.blocks import (  # noqa: F401
        BaseBlock
    )
    from evm.rlp.transactions import (  # noqa: F401
        BaseTransaction
    )


class BaseAsyncChainDB(BaseChainDB):
    #
    # Uncles API
    #
    @abstractmethod
    async def coro_get_block_uncles(self, uncles_hash: Hash32) -> List[BlockHeader]:
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Block API
    #
    @abstractmethod
    async def coro_persist_block(self, block: 'BaseBlock') -> None:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    async def coro_persist_uncles(self, uncles: Tuple[BlockHeader]) -> Hash32:
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Transaction API
    #
    @abstractmethod
    async def coro_add_receipt(self,
                               block_header: BlockHeader,
                               index_key: int, receipt: Receipt) -> Hash32:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    async def coro_add_transaction(self,
                                   block_header: BlockHeader,
                                   index_key: int, transaction: 'BaseTransaction') -> Hash32:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    async def coro_get_block_transactions(
            self,
            block_header: BlockHeader,
            transaction_class: Type['BaseTransaction']) -> Iterable['BaseTransaction']:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    async def coro_get_block_transaction_hashes(self, block_header: BlockHeader) -> Iterable[Hash32]:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    async def coro_get_receipts(self,
                                header: BlockHeader,
                                receipt_class: Type[Receipt]) -> Iterable[Receipt]:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    async def coro_get_transaction_by_index(
            self,
            block_number: BlockNumber,
            transaction_index: int,
            transaction_class: Type['BaseTransaction']) -> 'BaseTransaction':
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    async def coro_get_transaction_index(self,
                                         transaction_hash: Hash32) -> Tuple[BlockNumber, int]:
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Raw Database API
    #
    @abstractmethod
    async def coro_exists(self, key: bytes) -> bool:
        raise NotImplementedError("ChainDB classes must implement this method")

    @abstractmethod
    async def coro_persist_trie_data_dict(self, trie_data_dict: Dict[bytes, bytes]) -> None:
        raise NotImplementedError("ChainDB classes must implement this method")


class AsyncChainDB(ChainDB, BaseAsyncChainDB):
    #
    # Uncles API
    #
    async def coro_get_block_uncles(self, uncles_hash: Hash32) -> List[BlockHeader]:
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Block API
    #
    async def coro_persist_block(self, block: 'BaseBlock') -> None:
        raise NotImplementedError("ChainDB classes must implement this method")

    async def coro_persist_uncles(self, uncles: Tuple[BlockHeader]) -> Hash32:
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Transaction API
    #
    async def coro_add_receipt(self,
                               block_header: BlockHeader,
                               index_key: int, receipt: Receipt) -> Hash32:
        raise NotImplementedError("ChainDB classes must implement this method")

    async def coro_add_transaction(self,
                                   block_header: BlockHeader,
                                   index_key: int, transaction: 'BaseTransaction') -> Hash32:
        raise NotImplementedError("ChainDB classes must implement this method")

    async def coro_get_block_transactions(
            self,
            block_header: BlockHeader,
            transaction_class: Type['BaseTransaction']) -> Iterable['BaseTransaction']:
        raise NotImplementedError("ChainDB classes must implement this method")

    async def coro_get_block_transaction_hashes(self, block_header: BlockHeader) -> Iterable[Hash32]:
        raise NotImplementedError("ChainDB classes must implement this method")

    async def coro_get_receipts(self,
                                header: BlockHeader,
                                receipt_class: Type[Receipt]) -> Iterable[Receipt]:
        raise NotImplementedError("ChainDB classes must implement this method")

    async def coro_get_transaction_by_index(
            self,
            block_number: BlockNumber,
            transaction_index: int,
            transaction_class: Type['BaseTransaction']) -> 'BaseTransaction':
        raise NotImplementedError("ChainDB classes must implement this method")

    async def coro_get_transaction_index(self, transaction_hash: Hash32) -> Tuple[BlockNumber, int]:
        raise NotImplementedError("ChainDB classes must implement this method")

    #
    # Raw Database API
    #
    async def coro_exists(self, key: bytes) -> bool:
        raise NotImplementedError("ChainDB classes must implement this method")

    async def coro_persist_trie_data_dict(self, trie_data_dict: Dict[bytes, bytes]) -> None:
        raise NotImplementedError("ChainDB classes must implement this method")


class AsyncChainDBProxy(BaseProxy, BaseAsyncChainDB):
    coro_get_block_uncles = async_method('get_block_uncles')
    coro_persist_block = async_method('persist_block')
    coro_persist_uncles = async_method('persist_uncles')
    coro_add_receipt = async_method('add_receipt')
    coro_add_transaction = async_method('add_transaction')
    coro_get_block_transactions = async_method('get_block_transactions')
    coro_get_block_transaction_hashes = async_method('get_block_transaction_hashes')
    coro_get_receipts = async_method('get_receipts')
    coro_get_transaction_by_index = async_method('get_transaction_by_index')
    coro_get_transaction_index = async_method('get_transaction_index')
    coro_exists = async_method('exists')
    coro_persist_trie_data_dict = async_method('persist_trie_data_dict')

    get_block_uncles = sync_method('get_block_uncles')
    persist_block = sync_method('persist_block')
    persist_uncles = sync_method('persist_uncles')
    add_receipt = sync_method('add_receipt')
    add_transaction = sync_method('add_transaction')
    get_block_transactions = sync_method('get_block_transactions')
    get_block_transaction_hashes = sync_method('get_block_transaction_hashes')
    get_receipts = sync_method('get_receipts')
    get_transaction_by_index = sync_method('get_transaction_by_index')
    get_transaction_index = sync_method('get_transaction_index')
    exists = sync_method('exists')
    persist_trie_data_dict = sync_method('persist_trie_data_dict')
