from eth_utils import decode_hex
from eth_keys import keys

from evm.db.chain import AsyncChainDB

from p2p import kademlia
from p2p.peer import PeerPool


class LocalGethPeerPool(PeerPool):
    min_peers = 1

    async def get_nodes_to_connect(self):
        nodekey = keys.PrivateKey(decode_hex(
            "45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8"))
        remoteid = nodekey.public_key.to_hex()
        return [
            kademlia.Node(
                keys.PublicKey(decode_hex(remoteid)),
                kademlia.Address('127.0.0.1', 30303, 30303))
        ]


class FakeAsyncChainDB(AsyncChainDB):
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

    async def coro_persist_header_to_db(self, *args, **kwargs):
        return self.persist_header_to_db(*args, **kwargs)
