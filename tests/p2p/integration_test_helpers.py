import asyncio

from evm import MainnetChain, RopstenChain
from evm.chains.base import (
    MiningChain,
)
from evm.db.chain import AsyncChainDB

from p2p.exceptions import OperationCancelled

from trinity.db.header import AsyncHeaderDB


async def connect_to_peers_loop(peer_pool, nodes):
    """Loop forever trying to connect to one of the given nodes if the pool is not yet full."""
    while not peer_pool.cancel_token.triggered:
        try:
            if not peer_pool.is_full:
                await peer_pool.connect_to_nodes(nodes)
            await peer_pool.wait(asyncio.sleep(2))
        except OperationCancelled:
            break


def async_passthrough(base_name):
    coro_name = 'coro_{0}'.format(base_name)

    async def passthrough_method(self, *args, **kwargs):
        return getattr(self, base_name)(*args, **kwargs)
    passthrough_method.__name__ = coro_name
    return passthrough_method


class FakeAsyncChainDB(AsyncChainDB):
    coro_get_score = async_passthrough('get_score')
    coro_get_block_header_by_hash = async_passthrough('get_block_header_by_hash')
    coro_get_canonical_head = async_passthrough('get_canonical_head')
    coro_header_exists = async_passthrough('header_exists')
    coro_get_canonical_block_hash = async_passthrough('get_canonical_block_hash')
    coro_persist_header = async_passthrough('persist_header')
    coro_persist_uncles = async_passthrough('persist_uncles')
    coro_persist_trie_data_dict = async_passthrough('persist_trie_data_dict')
    coro_get_canonical_block_header_by_number = async_passthrough(
        'get_canonical_block_header_by_number')
    coro_get_block_transactions = async_passthrough('get_block_transactions')
    coro_get_block_uncles = async_passthrough('get_block_uncles')
    coro_get_receipts = async_passthrough('get_receipts')


async def coro_import_block(chain, block, perform_validation=True):
    # Be nice and yield control to give other coroutines a chance to run before us as
    # importing a block is a very expensive operation.
    await asyncio.sleep(0)
    return chain.import_block(block, perform_validation=perform_validation)


class FakeAsyncRopstenChain(RopstenChain):
    chaindb_class = FakeAsyncChainDB
    coro_import_block = coro_import_block
    coro_validate_chain = async_passthrough('validate_chain')


class FakeAsyncMainnetChain(MainnetChain):
    chaindb_class = FakeAsyncChainDB
    coro_import_block = coro_import_block
    coro_validate_chain = async_passthrough('validate_chain')


class FakeAsyncChain(MiningChain):
    coro_import_block = coro_import_block
    coro_validate_chain = async_passthrough('validate_chain')


class FakeAsyncHeaderDB(AsyncHeaderDB):
    coro_get_canonical_block_hash = async_passthrough('get_canonical_block_hash')
    coro_get_canonical_block_header_by_number = async_passthrough('get_canonical_block_header_by_number')  # noqa: E501
    coro_get_canonical_head = async_passthrough('get_canonical_head')
    coro_get_block_header_by_hash = async_passthrough('get_block_header_by_hash')
    coro_get_score = async_passthrough('get_score')
    coro_header_exists = async_passthrough('header_exists')
    coro_persist_header = async_passthrough('persist_header')
