from contextlib import contextmanager
from cytoolz import (
    identity,
)

from eth_utils import (
    decode_hex,
    encode_hex,
    int_to_big_endian,
    is_integer,
)

from evm.rpc.format import (
    block_to_dict,
    header_to_dict,
    format_params,
    to_int_if_hex,
)
from evm.rpc.modules import (
    RPCModule,
)


def get_header(chain, at_block):
    if at_block == 'pending':
        at_header = chain.header
    elif at_block == 'latest':
        at_header = chain.get_canonical_head()
    elif at_block == 'earliest':
        # TODO find if genesis block can be non-zero. Why does 'earliest' option even exist?
        at_header = chain.get_canonical_block_by_number(0).header
    elif is_integer(at_block) and at_block >= 0:
        at_header = chain.get_canonical_block_by_number(at_block).header
    else:
        raise TypeError("Unrecognized block reference: %r" % at_block)

    return at_header


@contextmanager
def state_at_block(chain, at_block, read_only=True):
    at_header = get_header(chain, at_block)
    vm = chain.get_vm(at_header)
    with vm.state_db(read_only=read_only) as state:
        yield state


def block_at_number(chain, at_block):
    if isinstance(at_block, int):
        block = chain.get_canonical_block_by_number(at_block)
    else:
        at_header = get_header(chain, at_block)
        vm = chain.get_vm(at_header)
        block = vm.get_block_by_header(at_header)
    return block


class Eth(RPCModule):
    '''
    All the methods defined by JSON-RPC API, starting with "eth_"...

    Any attribute without an underscore is publicly accessible.
    '''

    def accounts(self):
        raise NotImplementedError()

    def blockNumber(self):
        num = self._chain.get_canonical_head().block_number
        return hex(num)

    def coinbase(self):
        raise NotImplementedError()

    def gasPrice(self):
        raise NotImplementedError()

    @format_params(decode_hex, to_int_if_hex)
    def getBalance(self, address, at_block):
        with state_at_block(self._chain, at_block) as state:
            balance = state.get_balance(address)

        return hex(balance)

    @format_params(decode_hex, identity)
    def getBlockByHash(self, block_hash, include_transactions):
        block = self._chain.get_block_by_hash(block_hash)
        return block_to_dict(block, self._chain, include_transactions)

    @format_params(to_int_if_hex, identity)
    def getBlockByNumber(self, at_block, include_transactions):
        block = block_at_number(self._chain, at_block)
        return block_to_dict(block, self._chain, include_transactions)

    @format_params(decode_hex)
    def getBlockTransactionCountByHash(self, block_hash):
        block = self._chain.get_block_by_hash(block_hash)
        return hex(len(block.transactions))

    @format_params(to_int_if_hex)
    def getBlockTransactionCountByNumber(self, at_block):
        block = block_at_number(self._chain, at_block)
        return hex(len(block.transactions))

    @format_params(decode_hex, to_int_if_hex)
    def getCode(self, address, at_block):
        with state_at_block(self._chain, at_block) as state:
            code = state.get_code(address)
        return encode_hex(code)

    @format_params(decode_hex, to_int_if_hex, to_int_if_hex)
    def getStorageAt(self, address, position, at_block):
        if not isinstance(position, int):
            raise TypeError("Position of storage lookup must be an integer, but was: %r" % position)

        with state_at_block(self._chain, at_block) as state:
            stored_val = state.get_storage(address, position)
        return encode_hex(int_to_big_endian(stored_val))

    @format_params(decode_hex, to_int_if_hex)
    def getTransactionCount(self, address, at_block):
        with state_at_block(self._chain, at_block) as state:
            nonce = state.get_nonce(address)
        return hex(nonce)

    @format_params(decode_hex)
    def getUncleCountByBlockHash(self, block_hash):
        block = self._chain.get_block_by_hash(block_hash)
        return hex(len(block.uncles))

    @format_params(to_int_if_hex)
    def getUncleCountByBlockNumber(self, at_block):
        header = get_header(self._chain, at_block)
        block = self._chain.get_block_by_header(header)
        return hex(len(block.uncles))

    @format_params(decode_hex, to_int_if_hex)
    def getUncleByBlockHashAndIndex(self, block_hash, index):
        block = self._chain.get_block_by_hash(block_hash)
        uncle = block.uncles[index]
        return header_to_dict(uncle)

    @format_params(to_int_if_hex, to_int_if_hex)
    def getUncleByBlockNumberAndIndex(self, at_block, index):
        header = get_header(self._chain, at_block)
        block = self._chain.get_block_by_header(header)
        uncle = block.uncles[index]
        return header_to_dict(uncle)

    def hashrate(self):
        raise NotImplementedError()

    def mining(self):
        return False

    def protocolVersion(self):
        return "63"

    def syncing(self):
        raise NotImplementedError()
