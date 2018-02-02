from eth_utils import decode_hex
from eth_keys import keys
from evm.p2p import kademlia
from evm.p2p.peer import PeerPool


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
