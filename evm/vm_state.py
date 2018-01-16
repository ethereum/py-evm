from contextlib import contextmanager
import copy
import logging

from cytoolz import (
    merge,
)
from eth_utils import (
    encode_hex,
)

from evm.constants import (
    MAX_PREV_HEADER_DEPTH,
)
from evm.db.tracked import (
    AccessLogs,
)
from evm.exceptions import (
    BlockNotFound,
)
from evm.utils.state import (
    make_trie_root_and_nodes,
)


class BaseVMState(object):
    #
    # Set from __init__
    #
    _chaindb = None
    block_header = None
    prev_headers = None

    computation_class = None
    access_logs = None
    receipts = None

    def __init__(self, chaindb, block_header, prev_headers, receipts=[]):
        self._chaindb = chaindb
        self.block_header = block_header
        self.prev_headers = prev_headers

        self.access_logs = AccessLogs()
        self.receipts = receipts

    #
    # Logging
    #
    @property
    def logger(self):
        return logging.getLogger('evm.vm_state.{0}'.format(self.__class__.__name__))

    #
    # Block Object Properties (in opcodes)
    #
    @property
    def blockhash(self):
        return self.block_header.hash

    @property
    def coinbase(self):
        return self.block_header.coinbase

    @property
    def timestamp(self):
        return self.block_header.timestamp

    @property
    def block_number(self):
        return self.block_header.block_number

    @property
    def difficulty(self):
        return self.block_header.difficulty

    @property
    def gas_limit(self):
        return self.block_header.gas_limit

    #
    # state_db
    #
    @contextmanager
    def state_db(self, read_only=False):
        state = self._chaindb.get_state_db(self.block_header.state_root, read_only)
        yield state

        if read_only:
            # This acts as a secondary check that no mutation took place for
            # read_only databases.
            assert state.root_hash == self.block_header.state_root
        elif self.block_header.state_root != state.root_hash:
            self.block_header.state_root = state.root_hash

        self.access_logs.reads.update(state.db.access_logs.reads)
        self.access_logs.writes.update(state.db.access_logs.writes)

        # remove the reference to the underlying `db` object to ensure that no
        # further modifications can occur using the `State` object after
        # leaving the context.
        state.db = None
        state._trie = None

    #
    # Access self._chaindb
    #
    def snapshot(self):
        """
        Perform a full snapshot of the current state.

        Snapshots are a combination of the state_root at the time of the
        snapshot and the checkpoint_id returned from the journaled DB.
        """
        return (self.block_header.state_root, self._chaindb.snapshot())

    def revert(self, snapshot):
        """
        Revert the VM to the state at the snapshot
        """
        state_root, checkpoint_id = snapshot

        with self.state_db() as state_db:
            # first revert the database state root.
            state_db.root_hash = state_root

        # now roll the underlying database back
        self._chaindb.revert(checkpoint_id)

    def commit(self, snapshot):
        """
        Commits the journal to the point where the snapshot was taken.  This
        will destroy any journal checkpoints *after* the snapshot checkpoint.
        """
        _, checkpoint_id = snapshot
        self._chaindb.commit(checkpoint_id)

    def is_key_exists(self, key):
        """
        Check if the given key exsits in chaindb
        """
        return self._chaindb.exists(key)

    #
    # Access self.prev_headers (Read-only)
    #
    @property
    def parent_header(self):
        return self.prev_headers[0]

    def get_ancestor_hash(self, block_number):
        """
        Return the hash of the ancestor with the given block number.
        """
        ancestor_depth = self.block_header.block_number - block_number - 1
        if (ancestor_depth >= MAX_PREV_HEADER_DEPTH or
                ancestor_depth < 0 or
                ancestor_depth >= len(self.prev_headers)):
            return b''
        header = self.prev_headers[ancestor_depth]
        return header.hash

    def get_block_header_by_hash(self, block_hash):
        """
        Returns the block header by hash.
        """
        for value in self.prev_headers:
            if value.hash == block_hash:
                return value
        raise BlockNotFound(
            "No block header with hash {0} found in self.perv_headers".format(
                encode_hex(block_hash),
            )
        )

    #
    # Computation
    #
    def get_computation(self, message):
        """Return state object
        """
        if self.computation_class is None:
            raise AttributeError("No `computation_class` has been set for this VMState")
        else:
            computation = self.computation_class(self, message)
        return computation

    #
    # Execution
    #
    def apply_transaction(
            self,
            transaction,
            block,
            is_stateless=True):
        """
        Apply transaction to the given block

        :param transaction: the transaction need to be applied
        :param block: the block which the transaction applies on
        :param is_stateless: if is_stateless, call self.add_transaction to set block
        :type transaction: Transaction
        :type block: Block
        :type is_stateless: bool

        :return: the computation, applied block, and the trie_data
        :rtype: (Computation, Block, dict[bytes, bytes])
        """
        if is_stateless:
            # Don't modify the given block
            block = copy.deepcopy(block)
            self.block_header = block.header
            computation, block_header = self.execute_transaction(transaction)

            # Set block.
            block.header = block_header
            block, trie_data = self.add_transaction(transaction, computation, block)

            return computation, block, trie_data
        else:
            computation, block_header = self.execute_transaction(transaction)
            return computation, None, None

    def add_transaction(self, transaction, computation, block):
        """
        Add a transaction to the given block and
        return `trie_data` to store the transaction data in chaindb in VM layer.

        Update the bloom_filter, transaction trie and receipt trie roots, bloom_filter,
        bloom, and used_gas of the block.

        :param transaction: the executed transaction
        :param computation: the Computation object with executed result
        :param block: the Block which the transaction is added in
        :type transaction: Transaction
        :type computation: Computation
        :type block: Block

        :return: the block and the trie_data
        :rtype: (Block, dict[bytes, bytes])
        """
        receipt = self.make_receipt(transaction, computation)
        self.add_receipt(receipt)

        block.transactions.append(transaction)

        # Get trie roots and changed key-values.
        tx_root_hash, tx_kv_nodes = make_trie_root_and_nodes(block.transactions)
        receipt_root_hash, receipt_kv_nodes = make_trie_root_and_nodes(self.receipts)

        trie_data = merge(tx_kv_nodes, receipt_kv_nodes)

        block.bloom_filter |= receipt.bloom

        block.header.transaction_root = tx_root_hash
        block.header.receipt_root = receipt_root_hash
        block.header.bloom = int(block.bloom_filter)
        block.header.gas_used = receipt.gas_used

        return block, trie_data

    def add_receipt(self, receipt):
        self.receipts.append(receipt)

    def execute_transaction(self, transaction):
        """
        Execute the transaction in the vm.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def make_receipt(self, transaction, computation):
        """
        Make receipt.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def validate_block(self, block):
        """
        Validate the block.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def validate_uncle(self, block, uncle):
        """
        Validate the uncle.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    def validate_transaction(self, transaction):
        """
        Perform chain-aware validation checks on the transaction.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # classmethod
    #
    @classmethod
    def configure(cls,
                  name,
                  **overrides):
        """
        Class factory method for simple inline subclassing.
        """
        for key in overrides:
            if not hasattr(cls, key):
                raise TypeError(
                    "The State.configure cannot set attributes that are not "
                    "already present on the base class.  The attribute `{0}` was "
                    "not found on the base class `{1}`".format(key, cls)
                )
        return type(name, (cls,), overrides)
