import json

from eth_utils import (
    decode_hex,
    encode_hex,
    int_to_big_endian,
)

import rlp


def generate_response(request):
    return {
        'id': request['id'],
        'jsonrpc': request['jsonrpc'],
    }


def block_to_dict(block, chain, include_transactions):
    logs_bloom = encode_hex(int_to_big_endian(block.header.bloom))[2:]
    logs_bloom = '0x' + logs_bloom.rjust(512, '0')
    block_dict = {
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
        "totalDifficulty": hex(chain.chaindb.get_score(block.hash)),
        "transactionsRoot": encode_hex(block.header.transaction_root),
        "uncles": [encode_hex(uncle.hash) for uncle in block.uncles],
        "size": hex(len(rlp.encode(block))),
        "miner": encode_hex(block.header.coinbase),
    }

    if include_transactions:
        # block_dict['transactions'] = map(transaction_to_dict, block.transactions)
        raise NotImplemented("Cannot return transaction object with block, yet")
    else:
        block_dict['transactions'] = [encode_hex(tx.hash) for tx in block.transactions]

    return block_dict


class RPCServer:
    '''
    This "server" accepts json strings requests and returns the appropriate json string response,
    meeting the protocol for JSON-RPC defined here: https://github.com/ethereum/wiki/wiki/JSON-RPC

    The key entry point for all requests is :meth:`RPCServer.request`, which
    then proxies to the appropriate method. For example, see
    :meth:`RPCServer.eth_getBlockByHash`.
    '''

    def __init__(self, chain):
        self.chain = chain

    def request(self, request_json):
        '''
        The key entry point for all incoming requests
        '''
        try:
            request = json.loads(request_json)
        except json.decoder.JSONDecodeError as e:
            raise ValueError("cannot parse json in %r" % request_json) from e
        if request.get('jsonrpc', None) != '2.0':
            raise NotImplemented("Only the 2.0 jsonrpc protocol is supported")
        response = generate_response(request)
        if not hasattr(self, request['method']):
            response['error'] = "Method %r not supported" % request['method']
        else:
            response['result'] = getattr(self, request['method'])(*request['params'])
        return json.dumps(response)

    def eth_getBlockByHash(self, block_hash_hex, include_transactions):
        block_hash = decode_hex(block_hash_hex)
        block = self.chain.get_block_by_hash(block_hash)
        assert block.hash == block_hash

        block_dict = block_to_dict(block, self.chain, include_transactions)

        return block_dict
