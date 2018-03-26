from typing import Type

from eth_utils import decode_hex
from eth_keys import datatypes, keys

from evm.db.chain import AsyncChainDB, NonJournaledAsyncChainDB

from p2p import kademlia
from p2p.peer import BasePeer, HardCodedNodesPeerPool


class LocalGethPeerPool(HardCodedNodesPeerPool):

    def __init__(self,
                 peer_class: Type[BasePeer],
                 chaindb: AsyncChainDB,
                 network_id: int,
                 privkey: datatypes.PrivateKey,
                 ) -> None:
        min_peers = 1
        super().__init__(peer_class, chaindb, network_id, privkey, min_peers)

    def get_nodes_to_connect(self):
        nodekey = keys.PrivateKey(decode_hex(
            "45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8"))
        remoteid = nodekey.public_key.to_hex()
        yield kademlia.Node(keys.PublicKey(decode_hex(remoteid)),
                            kademlia.Address('127.0.0.1', 30303, 30303))


class FakeAsyncChainDB(NonJournaledAsyncChainDB):
    async def coro_get_score(self, *args, **kwargs):
        return self.get_score(*args, **kwargs)

    async def coro_get_block_header_by_hash(self, *args, **kwargs):
        return self.get_block_header_by_hash(*args, **kwargs)

    async def coro_get_canonical_head(self, *args, **kwargs):
        return self.get_canonical_head(*args, **kwargs)

    async def coro_header_exists(self, *args, **kwargs):
        return self.header_exists(*args, **kwargs)

    async def coro_lookup_block_hash(self, *args, **kwargs):
        return self.lookup_block_hash(*args, **kwargs)

    async def coro_persist_header(self, *args, **kwargs):
        return self.persist_header(*args, **kwargs)

    async def coro_persist_uncles(self, *args, **kwargs):
        return self.persist_uncles(*args, **kwargs)

    async def coro_persist_trie_data_dict(self, *args, **kwargs):
        return self.persist_trie_data_dict(*args, **kwargs)
