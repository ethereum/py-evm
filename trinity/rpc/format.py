import functools
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Union,
)
from eth_utils.toolz import (
    compose,
    merge,
)

from eth_utils import (
    apply_formatters_to_dict,
    decode_hex,
    encode_hex,
    int_to_big_endian,
)

import rlp

from eth.constants import (
    CREATE_CONTRACT_ADDRESS,
)
from eth.rlp.blocks import (
    BaseBlock
)
from eth.rlp.headers import (
    BlockHeader
)
from eth.rlp.transactions import (
    BaseTransaction
)

from trinity.chains.base import BaseAsyncChain


def transaction_to_dict(transaction: BaseTransaction) -> Dict[str, str]:
    return dict(
        hash=encode_hex(transaction.hash),
        nonce=hex(transaction.nonce),
        gas=hex(transaction.gas),
        gasPrice=hex(transaction.gas_price),
        to=encode_hex(transaction.to),
        value=hex(transaction.value),
        input=encode_hex(transaction.data),
        r=hex(transaction.r),
        s=hex(transaction.s),
        v=hex(transaction.v),
    )


hexstr_to_int = functools.partial(int, base=16)


TRANSACTION_NORMALIZER = {
    'data': decode_hex,
    'from': decode_hex,
    'gas': hexstr_to_int,
    'gasPrice': hexstr_to_int,
    'nonce': hexstr_to_int,
    'to': decode_hex,
    'value': hexstr_to_int,
}

SAFE_TRANSACTION_DEFAULTS = {
    'data': b'',
    'to': CREATE_CONTRACT_ADDRESS,
    'value': 0,
}


def normalize_transaction_dict(transaction_dict: Dict[str, str]) -> Dict[str, Any]:
    normalized_dict = apply_formatters_to_dict(TRANSACTION_NORMALIZER, transaction_dict)
    return merge(SAFE_TRANSACTION_DEFAULTS, normalized_dict)


def header_to_dict(header: BlockHeader) -> Dict[str, str]:
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


def block_to_dict(block: BaseBlock,
                  chain: BaseAsyncChain,
                  include_transactions: bool) -> Dict[str, Union[str, List[str]]]:

    header_dict = header_to_dict(block.header)

    block_dict: Dict[str, Union[str, List[str]]] = dict(
        header_dict,
        totalDifficulty=hex(chain.get_score(block.hash)),
        uncles=[encode_hex(uncle.hash) for uncle in block.uncles],
        size=hex(len(rlp.encode(block))),
    )

    if include_transactions:
        # block_dict['transactions'] = map(transaction_to_dict, block.transactions)
        raise NotImplementedError("Cannot return transaction object with block, yet")
    else:
        block_dict['transactions'] = [encode_hex(tx.hash) for tx in block.transactions]

    return block_dict


def format_params(*formatters: Any) -> Callable[..., Any]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def formatted_func(self: Any, *args: Any) -> Callable[..., Any]:
            if len(formatters) != len(args):
                raise TypeError("could not apply %d formatters to %r" % (len(formatters), args))
            formatted = (formatter(arg) for formatter, arg in zip(formatters, args))
            return await func(self, *formatted)
        return formatted_func
    return decorator


def to_int_if_hex(value: Any) -> Any:
    if isinstance(value, str) and value.startswith('0x'):
        return int(value, 16)
    else:
        return value


def empty_to_0x(val: str) -> str:
    if val:
        return val
    else:
        return '0x'


remove_leading_zeros = compose(hex, functools.partial(int, base=16))
