from contextlib import contextmanager
import copy
import logging

from cytoolz import (
    merge,
)
from eth_utils import (
    encode_hex,
)
import rlp
from trie import (
    HexaryTrie,
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


class BaseVMState(object):
    #
    # Set from __init__
    #
    _chaindb = None
    block_header = None
    prev_headers = None

    computation_class = None
    access_logs = None

    def __init__(self, chaindb, block_header, prev_headers):
        self._chaindb = chaindb
        self.block_header = block_header
        self.prev_headers = prev_headers

        self.access_logs = AccessLogs()

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
    # chaindb
    #
    def set_chaindb(self, db):
        self._chaindb = db

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
    # Snapshot and Revert
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

    #
    # Access self.prev_headers (Read-only)
    #
    def get_ancestor_hash(self, block_number):
        """
        Return the hash for the ancestor with the given block number.
        """
        ancestor_depth = self.block_header.block_number - block_number
        if ancestor_depth > MAX_PREV_HEADER_DEPTH or ancestor_depth < 1:
            return b''
        header = self.get_block_header_by_hash(self.block_header.parent_hash)
        while header.block_number != block_number:
            header = self.get_block_header_by_hash(header.parent_hash)
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

    def get_parent_header(self, block_header):
        """
        Returns the header for the parent block.
        """
        return self.get_block_header_by_hash(block_header.parent_hash)

    def is_key_exists(self, key):
        """
        Check if the given key exsits in chaindb
        """
        return self._chaindb.exists(key)

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
    @classmethod
    def apply_transaction(
            cls,
            vm_state,
            transaction,
            block,
            is_stateless=True,
            witness_db=None):
        """
        Apply transaction
        """
        if is_stateless:
            # Update block in this level.
            assert witness_db is not None

            # Don't change the given vm_state and block.
            vm_state = copy.deepcopy(vm_state)
            block = copy.deepcopy(block)

            vm_state.set_chaindb(witness_db)
            cls.block_header = block.header

            computation, block_header = cls.execute_transaction(vm_state, transaction)

            # Set block.
            block.header = block_header
            block, trie_data = cls.add_transaction(vm_state, transaction, computation, block)

            return computation, block, trie_data
        else:
            computation, block_header = cls.execute_transaction(vm_state, transaction)
            return computation, None, None

    @classmethod
    def add_transaction(cls, vm_state, transaction, computation, block):
        """
        Add a transaction to the given block and save the block data into chaindb.
        """
        receipt = cls.make_receipt(vm_state, transaction, computation)
        transaction_idx = len(block.transactions)

        index_key = rlp.encode(transaction_idx, sedes=rlp.sedes.big_endian_int)

        block.transactions.append(transaction)

        # Get trie roots and changed key-values.
        tx_root_hash, tx_db = cls.add_trie_node_to_db(
            block.header.transaction_root,
            index_key,
            transaction,
            block.db,
        )
        receipt_root_hash, receipt_db = cls.add_trie_node_to_db(
            block.header.receipt_root,
            index_key,
            receipt,
            block.db,
        )
        trie_data = merge(tx_db.wrapped_db.kv_store, receipt_db.wrapped_db.kv_store)

        block.bloom_filter |= receipt.bloom

        block.header.transaction_root = tx_root_hash
        block.header.receipt_root = receipt_root_hash
        block.header.bloom = int(block.bloom_filter)
        block.header.gas_used = receipt.gas_used

        return block, trie_data

    @staticmethod
    def add_trie_node_to_db(root_hash, index_key, node, db):
        """
        Add transaction or receipt to the given db.
        """
        trie_db = HexaryTrie(db, root_hash=root_hash)
        trie_db[index_key] = rlp.encode(node)
        return trie_db.root_hash, trie_db.db

    @staticmethod
    def execute_transaction(vm_state, transaction):
        """
        Execute the transaction in the vm.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @staticmethod
    def make_receipt(vm_state, transaction, computation):
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
