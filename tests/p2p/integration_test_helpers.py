import asyncio
from typing import Type

from eth_utils import decode_hex
from eth_keys import datatypes, keys

from evm import MainnetChain, RopstenChain

from p2p import kademlia
from p2p.peer import BasePeer, HardCodedNodesPeerPool

from trinity.db.chain import AsyncChainDB
from trinity.db.header import AsyncHeaderDB


def async_passthrough(base_name):
    coro_name = 'coro_{0}'.format(base_name)

    async def passthrough_method(self, *args, **kwargs):
        await asyncio.sleep(0)
        return getattr(self, base_name)(*args, **kwargs)
    passthrough_method.__name__ = coro_name
    return passthrough_method


class LocalGethPeerPool(HardCodedNodesPeerPool):

    def __init__(self,
                 peer_class: Type[BasePeer],
                 chaindb: AsyncChainDB,
                 network_id: int,
                 privkey: datatypes.PrivateKey,
                 ) -> None:
        min_peers = 1
        discovery = None
        super().__init__(peer_class, chaindb, network_id, privkey, discovery, min_peers)

    def get_nodes_to_connect(self):
        nodekey = keys.PrivateKey(decode_hex(
            "45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8"))
        remoteid = nodekey.public_key.to_hex()
        yield kademlia.Node(keys.PublicKey(decode_hex(remoteid)),
                            kademlia.Address('127.0.0.1', 30303, 30303))


class FakeAsyncChainDB(AsyncChainDB):
    coro_get_score = async_passthrough('get_score')
    coro_get_block_header_by_hash = async_passthrough('get_block_header_by_hash')
    coro_get_canonical_head = async_passthrough('get_canonical_head')
    coro_header_exists = async_passthrough('header_exists')
    coro_get_canonical_block_hash = async_passthrough('get_canonical_block_hash')
    coro_persist_header = async_passthrough('persist_header')
    coro_persist_uncles = async_passthrough('persist_uncles')
    coro_persist_trie_data_dict = async_passthrough('persist_trie_data_dict')


class FakeAsyncRopstenChain(RopstenChain):
    coro_import_block = async_passthrough('import_block')


class FakeAsyncMainnetChain(MainnetChain):
    coro_import_block = async_passthrough('import_block')


class FakeAsyncHeaderDB(AsyncHeaderDB):
    coro_get_canonical_block_hash = async_passthrough('get_canonical_block_hash')
    coro_get_canonical_block_header_by_number = async_passthrough('get_canonical_block_header_by_number')  # noqa: E501
    coro_get_canonical_head = async_passthrough('get_canonical_head')
    coro_get_block_header_by_hash = async_passthrough('get_block_header_by_hash')
    coro_get_score = async_passthrough('get_score')
    coro_header_exists = async_passthrough('header_exists')
    coro_persist_header = async_passthrough('persist_header')
