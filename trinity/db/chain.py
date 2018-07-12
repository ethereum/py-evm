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

from eth.db.chain import ChainDB
from eth.rlp.blocks import BaseBlock
from eth.rlp.headers import BlockHeader
from eth.rlp.receipts import Receipt
from eth.rlp.transactions import BaseTransaction

from trinity.db.header import AsyncHeaderDB
from trinity.utils.mp import (
    async_method,
    sync_method,
)


class AsyncChainDB(ChainDB, AsyncHeaderDB):
    async def coro_get(self, key: bytes) -> bytes:
        raise NotImplementedError()

    async def coro_persist_block(self, block: BaseBlock) -> None:
        raise NotImplementedError()

    async def coro_persist_uncles(self, uncles: Tuple[BlockHeader]) -> Hash32:
        raise NotImplementedError()

    async def coro_persist_trie_data_dict(self, trie_data_dict: Dict[bytes, bytes]) -> None:
        raise NotImplementedError()

    async def coro_get_block_transactions(
            self,
            header: BlockHeader,
            transaction_class: Type[BaseTransaction]) -> Iterable[BaseTransaction]:
        raise NotImplementedError()

    async def coro_get_block_uncles(self, uncles_hash: Hash32) -> List[BlockHeader]:
        raise NotImplementedError()

    async def coro_get_receipts(
            self, header: BlockHeader, receipt_class: Type[Receipt]) -> List[Receipt]:
        raise NotImplementedError()


class ChainDBProxy(BaseProxy):
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

    get = sync_method('get')
    get_block_header_by_hash = sync_method('get_block_header_by_hash')
    get_canonical_head = sync_method('get_canonical_head')
    get_score = sync_method('get_score')
    header_exists = sync_method('header_exists')
    get_canonical_block_hash = sync_method('get_canonical_block_hash')
    persist_header = sync_method('persist_header')
    persist_uncles = sync_method('persist_uncles')
    persist_trie_data_dict = sync_method('persist_trie_data_dict')
