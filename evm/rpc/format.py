import functools

from cytoolz import (
    compose,
    identity,
)

from eth_utils import (
    add_0x_prefix,
    encode_hex,
    int_to_big_endian,
)

import rlp


def transaction_to_dict(transaction):
    return dict(
        hash=encode_hex(transaction.hash),
        nonce=hex(transaction.nonce),
        gasLimit=hex(transaction.gas),
        gasPrice=hex(transaction.gas_price),
        to=encode_hex(transaction.to),
        value=hex(transaction.value),
        input=encode_hex(transaction.data),
        r=hex(transaction.r),
        s=hex(transaction.s),
        v=hex(transaction.v),
    )


def header_to_dict(header):
    logs_bloom = encode_hex(int_to_big_endian(header.bloom))[2:]
    logs_bloom = '0x' + logs_bloom.rjust(512, '0')
    header_dict = {
        "difficulty": hex(header.difficulty),
        "extraData": encode_hex(header.extra_data),
        "gasLimit": hex(header.gas_limit),
        "gasUsed": hex(header.gas_used),
        "hash": encode_hex(header.hash),
        "logsBloom": logs_bloom,
        "mixHash": encode_hex(header.mix_hash),
        "nonce": encode_hex(header.nonce),
        "number": hex(header.block_number),
        "parentHash": encode_hex(header.parent_hash),
        "receiptsRoot": encode_hex(header.receipt_root),
        "sha3Uncles": encode_hex(header.uncles_hash),
        "stateRoot": encode_hex(header.state_root),
        "timestamp": hex(header.timestamp),
        "transactionsRoot": encode_hex(header.transaction_root),
        "miner": encode_hex(header.coinbase),
    }
    return header_dict


def block_to_dict(block, chain, include_transactions):
    header_dict = header_to_dict(block.header)

    block_dict = dict(
        header_dict,
        totalDifficulty=hex(chain.chaindb.get_score(block.hash)),
        uncles=[encode_hex(uncle.hash) for uncle in block.uncles],
        size=hex(len(rlp.encode(block))),
    )

    if include_transactions:
        # block_dict['transactions'] = map(transaction_to_dict, block.transactions)
        raise NotImplementedError("Cannot return transaction object with block, yet")
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


def empty_to_0x(val):
    if val:
        return val
    else:
        return '0x'


remove_leading_zeros = compose(hex, functools.partial(int, base=16))

RPC_STATE_NORMALIZERS = {
    'balance': remove_leading_zeros,
    'code': empty_to_0x,
    'nonce': remove_leading_zeros,
}


def fixture_state_in_rpc_format(state):
    return {
        key: RPC_STATE_NORMALIZERS.get(key, identity)(value)
        for key, value in state.items()
    }


RPC_BLOCK_REMAPPERS = {
    'bloom': 'logsBloom',
    'coinbase': 'miner',
    'transactionsTrie': 'transactionsRoot',
    'uncleHash': 'sha3Uncles',
    'receiptTrie': 'receiptsRoot',
}

RPC_BLOCK_NORMALIZERS = {
    'difficulty': remove_leading_zeros,
    'extraData': empty_to_0x,
    'gasLimit': remove_leading_zeros,
    'gasUsed': remove_leading_zeros,
    'number': remove_leading_zeros,
    'timestamp': remove_leading_zeros,
}


def fixture_block_in_rpc_format(state):
    return {
        RPC_BLOCK_REMAPPERS.get(key, key):
        RPC_BLOCK_NORMALIZERS.get(key, identity)(value)
        for key, value in state.items()
    }


RPC_TRANSACTION_REMAPPERS = {
    'data': 'input',
}

RPC_TRANSACTION_NORMALIZERS = {
    'nonce': remove_leading_zeros,
    'gasLimit': remove_leading_zeros,
    'gasPrice': remove_leading_zeros,
    'value': remove_leading_zeros,
    'data': empty_to_0x,
    'to': add_0x_prefix,
    'r': remove_leading_zeros,
    's': remove_leading_zeros,
    'v': remove_leading_zeros,
}


def fixture_transaction_in_rpc_format(state):
    return {
        RPC_TRANSACTION_REMAPPERS.get(key, key):
        RPC_TRANSACTION_NORMALIZERS.get(key, identity)(value)
        for key, value in state.items()
    }
