import os

from eth_utils.toolz import (
    identity,
)
from typing import (
    Any,
    cast,
    Dict,
    List,
    Union,
)
from mypy_extensions import (
    TypedDict,
)

from eth_typing import (
    Address,
    BlockNumber,
    Hash32,
)
from eth_utils import (
    decode_hex,
    encode_hex,
    int_to_big_endian,
    is_integer,
    to_wei,
)

from eth.constants import (
    ZERO_ADDRESS,
)
from eth.rlp.blocks import (
    BaseBlock
)
from eth.rlp.headers import (
    BlockHeader
)
from eth.vm.spoof import (
    SpoofTransaction,
)
from eth.vm.state import (
    BaseAccountDB
)

from trinity.constants import (
    TO_NETWORKING_BROADCAST_CONFIG,
)
from trinity.chains.base import BaseAsyncChain
from trinity.rpc.format import (
    block_to_dict,
    header_to_dict,
    format_params,
    normalize_transaction_dict,
    to_int_if_hex,
    transaction_to_dict,
)
from trinity.rpc.modules import (
    Eth1ChainRPCModule,
)
from trinity.sync.common.events import (
    SyncingRequest,
)
from trinity._utils.validation import (
    validate_transaction_call_dict,
    validate_transaction_gas_estimation_dict,
)


async def get_header(chain: BaseAsyncChain, at_block: Union[str, int]) -> BlockHeader:
    if at_block == 'pending':
        raise NotImplementedError("RPC interface does not support the 'pending' block at this time")
    elif at_block == 'latest':
        at_header = chain.get_canonical_head()
    elif at_block == 'earliest':
        # TODO find if genesis block can be non-zero. Why does 'earliest' option even exist?
        block = await chain.coro_get_canonical_block_by_number(BlockNumber(0))
        at_header = block.header
    # mypy doesn't have user defined type guards yet
    # https://github.com/python/mypy/issues/5206
    elif is_integer(at_block) and at_block >= 0:  # type: ignore
        block = await chain.coro_get_canonical_block_by_number(BlockNumber(0))
        at_header = block.header
    else:
        raise TypeError("Unrecognized block reference: %r" % at_block)

    return at_header


async def state_at_block(
        chain: BaseAsyncChain,
        at_block: Union[str, int],
        read_only: bool=True) ->BaseAccountDB:
    at_header = await get_header(chain, at_block)
    vm = chain.get_vm(at_header)
    return vm.state


async def get_block_at_number(chain: BaseAsyncChain, at_block: Union[str, int]) -> BaseBlock:
    # mypy doesn't have user defined type guards yet
    # https://github.com/python/mypy/issues/5206
    if is_integer(at_block) and at_block >= 0:  # type: ignore
        # optimization to avoid requesting block, then header, then block again
        return await chain.coro_get_canonical_block_by_number(cast(BlockNumber, at_block))
    else:
        at_header = await get_header(chain, at_block)
        return await chain.coro_get_block_by_header(at_header)


def dict_to_spoof_transaction(
        chain: BaseAsyncChain,
        header: BlockHeader,
        transaction_dict: Dict[str, Any]) -> SpoofTransaction:
    """
    Convert dicts used in calls & gas estimates into a spoof transaction
    """
    txn_dict = normalize_transaction_dict(transaction_dict)
    sender = txn_dict.get('from', ZERO_ADDRESS)

    if 'nonce' in txn_dict:
        nonce = txn_dict['nonce']
    else:
        vm = chain.get_vm(header)
        nonce = vm.state.get_nonce(sender)

    gas_price = txn_dict.get('gasPrice', 0)
    gas = txn_dict.get('gas', header.gas_limit)

    unsigned = chain.get_vm_class(header).create_unsigned_transaction(
        nonce=nonce,
        gas_price=gas_price,
        gas=gas,
        to=txn_dict['to'],
        value=txn_dict['value'],
        data=txn_dict['data'],
    )
    return SpoofTransaction(unsigned, from_=sender)


class Eth(Eth1ChainRPCModule):
    """
    All the methods defined by JSON-RPC API, starting with "eth_"...

    Any attribute without an underscore is publicly accessible.
    """

    async def accounts(self) -> List[str]:
        # trinity does not manage accounts for the user
        return []

    async def blockNumber(self) -> str:
        num = self.chain.get_canonical_head().block_number
        return hex(num)

    @format_params(identity, to_int_if_hex)
    async def call(self, txn_dict: Dict[str, Any], at_block: Union[str, int]) -> str:
        header = await get_header(self.chain, at_block)
        validate_transaction_call_dict(txn_dict, self.chain.get_vm(header))
        transaction = dict_to_spoof_transaction(self.chain, header, txn_dict)
        result = self.chain.get_transaction_result(transaction, header)
        return encode_hex(result)

    async def coinbase(self) -> str:
        # Trinity doesn't support mining yet and hence coinbase_address is default (ZERO_ADDRESS)
        coinbase_address = ZERO_ADDRESS
        return encode_hex(coinbase_address)

    @format_params(identity, to_int_if_hex)
    async def estimateGas(self, txn_dict: Dict[str, Any], at_block: Union[str, int]) -> str:
        header = await get_header(self.chain, at_block)
        validate_transaction_gas_estimation_dict(txn_dict, self.chain.get_vm(header))
        transaction = dict_to_spoof_transaction(self.chain, header, txn_dict)
        gas = self.chain.estimate_gas(transaction, header)
        return hex(gas)

    async def gasPrice(self) -> str:
        return hex(int(os.environ.get('TRINITY_GAS_PRICE', to_wei(1, 'gwei'))))

    @format_params(decode_hex, to_int_if_hex)
    async def getBalance(self, address: Address, at_block: Union[str, int]) -> str:
        state = await state_at_block(self.chain, at_block)
        balance = state.get_balance(address)

        return hex(balance)

    @format_params(decode_hex, identity)
    async def getBlockByHash(self,
                             block_hash: Hash32,
                             include_transactions: bool) -> Dict[str, Union[str, List[str]]]:
        block = await self.chain.coro_get_block_by_hash(block_hash)
        return block_to_dict(block, self.chain, include_transactions)

    @format_params(to_int_if_hex, identity)
    async def getBlockByNumber(self,
                               at_block: Union[str, int],
                               include_transactions: bool) -> Dict[str, Union[str, List[str]]]:
        block = await get_block_at_number(self.chain, at_block)
        return block_to_dict(block, self.chain, include_transactions)

    @format_params(decode_hex)
    async def getBlockTransactionCountByHash(self, block_hash: Hash32) -> str:
        block = await self.chain.coro_get_block_by_hash(block_hash)
        return hex(len(block.transactions))

    @format_params(to_int_if_hex)
    async def getBlockTransactionCountByNumber(self, at_block: Union[str, int]) -> str:
        block = await get_block_at_number(self.chain, at_block)
        return hex(len(block.transactions))

    @format_params(decode_hex, to_int_if_hex)
    async def getCode(self, address: Address, at_block: Union[str, int]) -> str:
        state = await state_at_block(self.chain, at_block)
        code = state.get_code(address)
        return encode_hex(code)

    @format_params(decode_hex, to_int_if_hex, to_int_if_hex)
    async def getStorageAt(self, address: Address, position: int, at_block: Union[str, int]) -> str:
        if not is_integer(position) or position < 0:
            raise TypeError("Position of storage must be a whole number, but was: %r" % position)

        state = await state_at_block(self.chain, at_block)
        stored_val = state.get_storage(address, position)
        return encode_hex(int_to_big_endian(stored_val))

    @format_params(decode_hex, to_int_if_hex)
    async def getTransactionByBlockHashAndIndex(self,
                                                block_hash: Hash32,
                                                index: int) -> Dict[str, str]:
        block = await self.chain.coro_get_block_by_hash(block_hash)
        transaction = block.transactions[index]
        return transaction_to_dict(transaction)

    @format_params(to_int_if_hex, to_int_if_hex)
    async def getTransactionByBlockNumberAndIndex(self,
                                                  at_block: Union[str, int],
                                                  index: int) -> Dict[str, str]:
        block = await get_block_at_number(self.chain, at_block)
        transaction = block.transactions[index]
        return transaction_to_dict(transaction)

    @format_params(decode_hex, to_int_if_hex)
    async def getTransactionCount(self, address: Address, at_block: Union[str, int]) -> str:
        state = await state_at_block(self.chain, at_block)
        nonce = state.get_nonce(address)
        return hex(nonce)

    @format_params(decode_hex)
    async def getUncleCountByBlockHash(self, block_hash: Hash32) -> str:
        block = await self.chain.coro_get_block_by_hash(block_hash)
        return hex(len(block.uncles))

    @format_params(to_int_if_hex)
    async def getUncleCountByBlockNumber(self, at_block: Union[str, int]) -> str:
        block = await get_block_at_number(self.chain, at_block)
        return hex(len(block.uncles))

    @format_params(decode_hex, to_int_if_hex)
    async def getUncleByBlockHashAndIndex(self, block_hash: Hash32, index: int) -> Dict[str, str]:
        block = await self.chain.coro_get_block_by_hash(block_hash)
        uncle = block.uncles[index]
        return header_to_dict(uncle)

    @format_params(to_int_if_hex, to_int_if_hex)
    async def getUncleByBlockNumberAndIndex(self,
                                            at_block: Union[str, int],
                                            index: int) -> Dict[str, str]:
        block = await get_block_at_number(self.chain, at_block)
        uncle = block.uncles[index]
        return header_to_dict(uncle)

    async def hashrate(self) -> str:
        # Trinity doesn't support mining yet and hence hashrate is default (0)
        hashrate = 0
        return hex(hashrate)

    async def mining(self) -> bool:
        return False

    async def protocolVersion(self) -> str:
        return "63"

    class SyncProgress(TypedDict):
        startingBlock: BlockNumber
        currentBlock: BlockNumber
        highestBlock: BlockNumber

    async def syncing(self) -> Union[bool, SyncProgress]:
        res = await self.event_bus.request(SyncingRequest(), TO_NETWORKING_BROADCAST_CONFIG)
        if res.is_syncing:
            return {
                "startingBlock": res.progress.starting_block,
                "currentBlock": res.progress.current_block,
                "highestBlock": res.progress.highest_block
            }
        return False
