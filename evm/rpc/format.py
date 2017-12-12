import functools

from eth_utils import (
    encode_hex,
    int_to_big_endian,
)

import rlp


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


def format_params(*formatters):
    def decorator(func):
        @functools.wraps(func)
        def formatted_func(self, *args):
            if len(formatters) != len(args):
                raise TypeError("could not apply %d formatters to %r" % (len(formatters), args))
            formatted = (formatter(arg) for formatter, arg in zip(formatters, args))
            return func(self, *formatted)
        return formatted_func
    return decorator


def to_int_if_hex(value):
    if isinstance(value, str) and value.startswith('0x'):
        return int(value, 16)
    else:
        return value
