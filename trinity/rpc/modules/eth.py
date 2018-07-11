from cytoolz import (
    identity,
)
from typing import (
    Dict,
    List,
    Union,
)

from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
    decode_hex,
    encode_hex,
    int_to_big_endian,
    is_integer,
)

from eth.chains.base import (
    BaseChain
)
from eth.rlp.blocks import (
    BaseBlock
)
from eth.rlp.headers import (
    BlockHeader
)
from eth.vm.state import (
    BaseAccountDB
)

from trinity.rpc.format import (
    block_to_dict,
    header_to_dict,
    format_params,
    to_int_if_hex,
    transaction_to_dict,
)
from trinity.rpc.modules import (
    RPCModule,
)


def get_header(chain: BaseChain, at_block: Union[str, int]) -> BlockHeader:
    if at_block == 'pending':
        raise NotImplementedError("RPC interface does not support the 'pending' block at this time")
    elif at_block == 'latest':
        at_header = chain.get_canonical_head()
    elif at_block == 'earliest':
        # TODO find if genesis block can be non-zero. Why does 'earliest' option even exist?
        at_header = chain.get_canonical_block_by_number(0).header
    # mypy doesn't have user defined type guards yet
    # https://github.com/python/mypy/issues/5206
    elif is_integer(at_block) and at_block >= 0:  # type: ignore
        at_header = chain.get_canonical_block_by_number(at_block).header
    else:
        raise TypeError("Unrecognized block reference: %r" % at_block)

    return at_header


def account_db_at_block(chain: BaseChain,
                        at_block: Union[str, int],
                        read_only: bool=True) ->BaseAccountDB:
    at_header = get_header(chain, at_block)
    vm = chain.get_vm(at_header)
    return vm.state.account_db


def get_block_at_number(chain: BaseChain, at_block: Union[str, int]) -> BaseBlock:
    # mypy doesn't have user defined type guards yet
    # https://github.com/python/mypy/issues/5206
    if is_integer(at_block) and at_block >= 0:  # type: ignore
        # optimization to avoid requesting block, then header, then block again
        return chain.get_canonical_block_by_number(at_block)
    else:
        at_header = get_header(chain, at_block)
        return chain.get_block_by_header(at_header)


class Eth(RPCModule):
    '''
    All the methods defined by JSON-RPC API, starting with "eth_"...

    Any attribute without an underscore is publicly accessible.
    '''

    def accounts(self) -> None:
        raise NotImplementedError()

    def blockNumber(self) -> str:
        num = self._chain.get_canonical_head().block_number
        return hex(num)

    def coinbase(self) -> Hash32:
        raise NotImplementedError()

    def gasPrice(self) -> int:
        raise NotImplementedError()

    @format_params(decode_hex, to_int_if_hex)
    def getBalance(self, address: Address, at_block: Union[str, int]) -> str:
        account_db = account_db_at_block(self._chain, at_block)
        balance = account_db.get_balance(address)

        return hex(balance)

    @format_params(decode_hex, identity)
    def getBlockByHash(self,
                       block_hash: Hash32,
                       include_transactions: bool) -> Dict[str, Union[str, List[str]]]:
        block = self._chain.get_block_by_hash(block_hash)
        return block_to_dict(block, self._chain, include_transactions)

    @format_params(to_int_if_hex, identity)
    def getBlockByNumber(self,
                         at_block: Union[str, int],
                         include_transactions: bool) -> Dict[str, Union[str, List[str]]]:
        block = get_block_at_number(self._chain, at_block)
        return block_to_dict(block, self._chain, include_transactions)

    @format_params(decode_hex)
    def getBlockTransactionCountByHash(self, block_hash: Hash32) -> str:
        block = self._chain.get_block_by_hash(block_hash)
        return hex(len(block.transactions))

    @format_params(to_int_if_hex)
    def getBlockTransactionCountByNumber(self, at_block: Union[str, int]) -> str:
        block = get_block_at_number(self._chain, at_block)
        return hex(len(block.transactions))

    @format_params(decode_hex, to_int_if_hex)
    def getCode(self, address: Address, at_block: Union[str, int]) -> str:
        account_db = account_db_at_block(self._chain, at_block)
        code = account_db.get_code(address)
        return encode_hex(code)

    @format_params(decode_hex, to_int_if_hex, to_int_if_hex)
    def getStorageAt(self, address: Address, position: int, at_block: Union[str, int]) -> str:
        if not is_integer(position) or position < 0:
            raise TypeError("Position of storage must be a whole number, but was: %r" % position)

        account_db = account_db_at_block(self._chain, at_block)
        stored_val = account_db.get_storage(address, position)
        return encode_hex(int_to_big_endian(stored_val))

    @format_params(decode_hex, to_int_if_hex)
    def getTransactionByBlockHashAndIndex(self, block_hash: Hash32, index: int) -> Dict[str, str]:
        block = self._chain.get_block_by_hash(block_hash)
        transaction = block.transactions[index]
        return transaction_to_dict(transaction)

    @format_params(to_int_if_hex, to_int_if_hex)
    def getTransactionByBlockNumberAndIndex(self,
                                            at_block: Union[str, int],
                                            index: int) -> Dict[str, str]:
        block = get_block_at_number(self._chain, at_block)
        transaction = block.transactions[index]
        return transaction_to_dict(transaction)

    @format_params(decode_hex, to_int_if_hex)
    def getTransactionCount(self, address: Address, at_block: Union[str, int]) -> str:
        account_db = account_db_at_block(self._chain, at_block)
        nonce = account_db.get_nonce(address)
        return hex(nonce)

    @format_params(decode_hex)
    def getUncleCountByBlockHash(self, block_hash: Hash32) -> str:
        block = self._chain.get_block_by_hash(block_hash)
        return hex(len(block.uncles))

    @format_params(to_int_if_hex)
    def getUncleCountByBlockNumber(self, at_block: Union[str, int]) -> str:
        block = get_block_at_number(self._chain, at_block)
        return hex(len(block.uncles))

    @format_params(decode_hex, to_int_if_hex)
    def getUncleByBlockHashAndIndex(self, block_hash: Hash32, index: int) -> Dict[str, str]:
        block = self._chain.get_block_by_hash(block_hash)
        uncle = block.uncles[index]
        return header_to_dict(uncle)

    @format_params(to_int_if_hex, to_int_if_hex)
    def getUncleByBlockNumberAndIndex(self,
                                      at_block: Union[str, int],
                                      index: int) -> Dict[str, str]:
        block = get_block_at_number(self._chain, at_block)
        uncle = block.uncles[index]
        return header_to_dict(uncle)

    def hashrate(self) -> str:
        raise NotImplementedError()

    def mining(self) -> bool:
        return False

    def protocolVersion(self) -> str:
        return "63"

    def syncing(self) -> bool:
        raise NotImplementedError()
