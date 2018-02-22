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

from eth_utils import (
    decode_hex,
    encode_hex,
    int_to_big_endian,
)

from p2p.lightchain import LightChain


class App(web.Application):
    allowed_methods = ['eth_getBlockByNumber', 'eth_getBlockByHash']

    def __init__(self, chain):
        super(App, self).__init__()
        self.chain = chain
        self.router.add_post('/', self.handle)
        self.on_startup.append(self.run_chain)
        self.on_shutdown.append(self.stop_chain)

    async def handle(self, request):
        body = await request.json()
        req_id = body['id']
        method = body['method']
        hash_or_number, _ = body['params']
        if method == 'eth_getBlockByNumber':
            if hash_or_number == "latest":
                head = self.chain.get_canonical_head()
                number = head.block_number
            else:
                number = int(hash_or_number, 16)
            block = await self.chain.get_canonical_block_by_number(number)
        elif method == 'eth_getBlockByHash':
            block_hash = decode_hex(hash_or_number)
            block = await self.chain.get_block_by_hash(block_hash)
        else:
            raise HTTPMethodNotAllowed(method, self.allowed_methods)

        block_dict = self._block_to_dict(block)
        response = {"jsonrpc": "2.0", "id": req_id, "result": block_dict}
        return web.json_response(response)

    async def run_chain(self, app):
        asyncio.ensure_future(self.chain.run())

    async def stop_chain(self, app):
        await self.chain.stop()

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


if __name__ == '__main__':
    import argparse
    from evm.chains.mainnet import (
        MAINNET_GENESIS_HEADER, MAINNET_VM_CONFIGURATION, MAINNET_NETWORK_ID)
    from evm.chains.ropsten import ROPSTEN_GENESIS_HEADER, ROPSTEN_NETWORK_ID
    from evm.db.backends.level import LevelDB
    from evm.db.chain import ChainDB
    from evm.exceptions import CanonicalHeadNotFound
    from p2p import ecies
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    logging.getLogger("p2p.lightchain").setLevel(logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument('-db', type=str, required=True)
    parser.add_argument('-mainnet', action="store_true")
    args = parser.parse_args()

    GENESIS_HEADER = ROPSTEN_GENESIS_HEADER
    NETWORK_ID = ROPSTEN_NETWORK_ID
    if args.mainnet:
        GENESIS_HEADER = MAINNET_GENESIS_HEADER
        NETWORK_ID = MAINNET_NETWORK_ID
    DemoLightChain = LightChain.configure(
        'RPCDemoLightChain',
        vm_configuration=MAINNET_VM_CONFIGURATION,
        network_id=NETWORK_ID,
        privkey=ecies.generate_privkey(),
    )

    chaindb = ChainDB(LevelDB(args.db))
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
