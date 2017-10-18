"""
A simple JSON-RPC server that only responds to eth_getBlockByNumber and eth_getBlockByHash
calls. It uses the LightChain to sync headers as they're announced and fetches blocks on demand
as RPC calls ask for them.
"""
import asyncio
import logging

import rlp

from aiohttp import web
from aiohttp.web_exceptions import HTTPMethodNotAllowed

from eth_utils import decode_hex, encode_hex

from eth_keys import keys

from evm.chains.mainnet import MAINNET_VM_CONFIGURATION
from evm.chains.ropsten import (
    ROPSTEN_GENESIS_HEADER,
    ROPSTEN_NETWORK_ID,
)
from evm.p2p import ecies
from evm.p2p import kademlia
from evm.p2p.constants import HANDSHAKE_TIMEOUT
from evm.p2p.lightchain import (
    LightChain,
    OnDemandDataBackend,
)
from evm.p2p.peer import (
    handshake,
    LESPeer,
)
from evm.utils.numeric import int_to_big_endian


# Change the values below to connect to a node on a different network or IP address.
GENESIS_HEADER = ROPSTEN_GENESIS_HEADER
NETWORK_ID = ROPSTEN_NETWORK_ID
# The pubkey for the local node we'll connect to. Simply pass the hex string below to
# geth using the "-nodekeyhex" argument.
NODE_ID = keys.PrivateKey(decode_hex(
    "45a915e4d060149eb4365960e6a7a45f334393093061116b197e3240065ff2d8")).public_key
NODE_ADDR = kademlia.Address('127.0.0.1', 30303, 30303)


class App(web.Application):
    allowed_methods = ['eth_getBlockByNumber', 'eth_getBlockByHash']

    def __init__(self, chain):
        super(App, self).__init__()
        self.chain = chain
        self.router.add_post('/', self.handle)
        self.on_startup.append(self.connect_peer)
        self.on_shutdown.append(self.stop_chain)

    @asyncio.coroutine
    def handle(self, request):
        body = yield from request.json()
        req_id = body['id']
        method = body['method']
        hash_or_number, _ = body['params']
        if method == 'eth_getBlockByNumber':
            if hash_or_number == "latest":
                head = self.chain.get_canonical_head()
                number = head.block_number
            else:
                number = int(hash_or_number, 16)
            block = yield from self.chain.get_canonical_block_by_number(number)
        elif method == 'eth_getBlockByHash':
            block_hash = decode_hex(hash_or_number)
            block = yield from self.chain.get_block_by_hash(block_hash)
        else:
            raise HTTPMethodNotAllowed(method, self.allowed_methods)

        block_dict = self._block_to_dict(block)
        response = {"jsonrpc": "2.0", "id": req_id, "result": block_dict}
        return web.json_response(response)

    @asyncio.coroutine
    def connect_peer(self, app):
        return self.chain.on_demand_data_backend.get_peer()

    @asyncio.coroutine
    def stop_chain(self, app):
        return self.chain.stop()

    def _block_to_dict(self, block):
        logs_bloom = encode_hex(int_to_big_endian(block.header.bloom))[2:]
        logs_bloom = '0x' + logs_bloom.rjust(512, '0')
        return {
            "difficulty": hex(block.header.difficulty),
            "extraData": encode_hex(block.header.extra_data),
            "gasLimit": hex(block.header.gas_limit),
            "gasUsed": hex(block.header.gas_used),
            "hash": encode_hex(block.header.hash),
            "logsBloom": logs_bloom,
            "mixHash": encode_hex(block.header.mix_hash),
            "nonce": encode_hex(block.header.nonce),
            "number": hex(block.header.block_number),
            "parentHash": encode_hex(block.header.parent_hash),
            "receiptsRoot": encode_hex(block.header.receipt_root),
            "sha3Uncles": encode_hex(block.header.uncles_hash),
            "stateRoot": encode_hex(block.header.state_root),
            "timestamp": hex(block.header.timestamp),
            "totalDifficulty": hex(self.chain.chaindb.get_score(block.hash)),
            "transactions": [encode_hex(tx.hash) for tx in block.transactions],
            "transactionsRoot": encode_hex(block.header.transaction_root),
            "uncles": [encode_hex(uncle.hash) for uncle in block.uncles],
            "size": hex(len(rlp.encode(block))),
            "miner": encode_hex(block.header.coinbase),
        }


class SinglePeerOnDemandDataBackend(OnDemandDataBackend):

    def __init__(self, chaindb):
        self.chaindb = chaindb
        self.privkey = ecies.generate_privkey()
        self._peer = None

    @asyncio.coroutine
    def get_peer(self):
        remote = kademlia.Node(NODE_ID, NODE_ADDR)
        if self._peer is None or self._peer.is_finished:
            self._peer = yield from asyncio.wait_for(
                handshake(remote, self.privkey, LESPeer, self.chaindb, NETWORK_ID),
                HANDSHAKE_TIMEOUT)
            asyncio.ensure_future(self._peer.start())
        return self._peer

    @asyncio.coroutine
    def stop(self):
        if self._peer is not None and not self._peer.is_finished:
            yield from self._peer.stop()


DemoLightChain = LightChain.configure(
    'RPCDemoLightChain',
    vm_configuration=MAINNET_VM_CONFIGURATION,
    on_demand_data_backend_class=SinglePeerOnDemandDataBackend,
    network_id=NETWORK_ID,
)


if __name__ == '__main__':
    import argparse
    from evm.db.backends.level import LevelDB
    from evm.db.chain import BaseChainDB
    from evm.exceptions import CanonicalHeadNotFound
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str, required=True)
    args = parser.parse_args()

    chaindb = BaseChainDB(LevelDB(args.db))
    try:
        chaindb.get_canonical_head()
    except CanonicalHeadNotFound:
        # We're starting with a fresh DB.
        chain = DemoLightChain.from_genesis_header(chaindb, GENESIS_HEADER)
    else:
        # We're reusing an existing db.
        chain = DemoLightChain(chaindb)

    app = App(chain)
    web.run_app(app, port=8080)
