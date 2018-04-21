from contextlib import contextmanager
from cytoolz import (
    identity,
)

from eth_utils import (
    decode_hex,
    encode_hex,
    int_to_big_endian,
    is_bytes,
    is_integer,
)

from trinity.rpc.format import (
    block_to_dict,
    header_to_dict,
    format_params,
    to_int_if_hex,
    transaction_to_dict,
)
# Tell mypy to ignore this import as a workaround for https://github.com/python/mypy/issues/4049
from trinity.rpc.modules import (  # type: ignore
    RPCModule,
)


def get_block(db, identifier):
    if identifier == 'pending':
        block = db.get_pending_block()
    elif identifier == 'latest':
        block = db.get_canonical_head_block()
    elif identifier == 'earliest':
        # Note: this assumes that the earliest block is always 0.
        block = db.get_block_by_number(0)
    elif is_integer(identifier) and identifier >= 0:
        block = db.get_block_by_number(identifier)
    elif is_bytes(identifier) and len(identifier) == 32:
        block = db.get_block_by_hash(identifier)
    else:
        raise TypeError("Unrecognized block reference: %r" % identifier)

    return block


@contextmanager
def state_at_block(chain, identifier, read_only=True):
    block = get_block(chain, identifier)
    vm = chain.get_vm(block.header)
    if read_only:
        yield vm.state.read_only_state_db
    else:
        with vm.state.mutable_state_db() as state:
            yield state


class Eth(RPCModule):
    '''
    All the methods defined by JSON-RPC API, starting with "eth_"...

    Any attribute without an underscore is publicly accessible.
    '''

    def accounts(self):
        raise NotImplementedError()

    def coinbase(self):
        raise NotImplementedError()

    def gasPrice(self):
        raise NotImplementedError()

    #
    # Blocks
    #
    def blockNumber(self):
        num = self._db
        num = self._db.get_canonical_head().block_number
        return hex(num)

    @format_params(decode_hex, identity)
    def getBlockByHash(self, block_hash, include_transactions):
        block = self._db.get_block_by_hash(block_hash)
        return block_to_dict(block, self._db, include_transactions)

    @format_params(to_int_if_hex, identity)
    def getBlockByNumber(self, at_block, include_transactions):
        block = get_block(self._db, at_block)
        return block_to_dict(block, self._db, include_transactions)

    @format_params(decode_hex)
    def getBlockTransactionCountByHash(self, block_hash):
        block = self._db.get_block_by_hash(block_hash)
        return hex(len(block.transactions))

    @format_params(to_int_if_hex)
    def getBlockTransactionCountByNumber(self, at_block):
        block = get_block(self._db, at_block)
        return hex(len(block.transactions))

    #
    # Accounts
    #
    @format_params(decode_hex, to_int_if_hex)
    def getBalance(self, address, at_block):
        account = self._db.get_account(address, at_block)
        return hex(account.balance)

    @format_params(decode_hex, to_int_if_hex)
    def getCode(self, address, at_block):
        account = self._db.get_account(address, at_block)
        return encode_hex(account.code)

    @format_params(decode_hex, to_int_if_hex, to_int_if_hex)
    def getStorageAt(self, address, position, at_block):
        if not is_integer(position) or position < 0:
            raise TypeError("Position of storage must be a whole number, but was: %r" % position)

        account = self._db.get_account(address, block)
        # TODO: a way to get storage values?
        raise NotImplementedError("not yet implemented")

    @format_params(decode_hex, to_int_if_hex)
    def getTransactionCount(self, address, at_block):
        account = self._db.get_account(address, block)
        return account.nonce

    #
    # Transactions and Receipts
    #
    @format_params(decode_hex, to_int_if_hex)
    def getTransactionByBlockHashAndIndex(self, block_hash, index):
        block = get_block(self._db, block_hash)
        transaction = block.transactions[index]
        return transaction_to_dict(transaction)

    @format_params(to_int_if_hex, to_int_if_hex)
    def getTransactionByBlockNumberAndIndex(self, at_block, index):
        block = get_block(self._db, at_block)
        transaction = block.transactions[index]
        return transaction_to_dict(transaction)

    #
    # Uncles
    #
    @format_params(decode_hex)
    def getUncleCountByBlockHash(self, block_hash):
        block = get_block(self._db, block_hash)
        return hex(len(block.uncles))

    @format_params(to_int_if_hex)
    def getUncleCountByBlockNumber(self, at_block):
        block = get_block(self._db, at_block)
        return hex(len(block.uncles))

    @format_params(decode_hex, to_int_if_hex)
    def getUncleByBlockHashAndIndex(self, block_hash, index):
        block = get_block(self._db, block_hash)
        uncle = block.uncles[index]
        return header_to_dict(uncle)

    @format_params(to_int_if_hex, to_int_if_hex)
    def getUncleByBlockNumberAndIndex(self, at_block, index):
        block = get_block(self._db, at_block)
        uncle = block.uncles[index]
        return header_to_dict(uncle)

    #
    # Mining
    #
    def hashrate(self):
        raise NotImplementedError()

    def mining(self):
        return False

    #
    # Meta
    #
    def protocolVersion(self):
        return "63"

    def syncing(self):
        raise NotImplementedError()
