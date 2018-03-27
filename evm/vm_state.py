from abc import (
    ABCMeta,
    abstractmethod
)
from contextlib import contextmanager
import logging
from typing import (  # noqa: F401
    Type,
    TYPE_CHECKING
)

from cytoolz import (
    merge,
)

from evm.constants import (
    MAX_PREV_HEADER_DEPTH,
)
from evm.db.tracked import (
    AccessLogs,
)
from evm.db.trie import (
    make_trie_root_and_nodes,
)
from evm.utils.datatypes import (
    Configurable,
)

if TYPE_CHECKING:
    from evm.rlp.blocks import (  # noqa: F401
        BaseBlock,
    )
    from evm.computation import (  # noqa: F401
        BaseComputation,
    )
    from evm.transaction_context import (  # noqa: F401
        BaseTransactionContext,
    )


class BaseVMState(Configurable, metaclass=ABCMeta):
    #
    # Set from __init__
    #
    _chaindb = None
    execution_context = None
    state_root = None
    receipts = None

    block_class = None  # type: Type[BaseBlock]
    computation_class = None  # type: Type[BaseComputation]
    trie_class = None
    transaction_context_class = None  # type: Type[BaseTransactionContext]
    access_logs = None

    def __init__(self, chaindb, execution_context, state_root, receipts=[]):
        self._chaindb = chaindb
        self.execution_context = execution_context
        self.state_root = state_root
        self.receipts = receipts
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
    def coinbase(self):
        return self.execution_context.coinbase

    @property
    def timestamp(self):
        return self.execution_context.timestamp

    @property
    def block_number(self):
        return self.execution_context.block_number

    @property
    def difficulty(self):
        return self.execution_context.difficulty

    @property
    def gas_limit(self):
        return self.execution_context.gas_limit

    #
    # Helpers
    #
    @property
    def gas_used(self):
        if self.receipts:
            return self.receipts[-1].gas_used
        else:
            return 0

    #
    # state_db
    #
    @contextmanager
    def state_db(self, read_only=False, access_list=None):
        state = self._chaindb.get_state_db(
            self.state_root,
            read_only,
            access_list=access_list
        )
        yield state

        if read_only:
            # This acts as a secondary check that no mutation took place for
            # read_only databases.
            assert state.root_hash == self.state_root
        elif self.state_root != state.root_hash:
            self.set_state_root(state.root_hash)

        self.access_logs.writes.update(state.db.access_logs.writes)
        self.access_logs.reads.update(state.db.access_logs.reads)

        # remove the reference to the underlying `db` object to ensure that no
        # further modifications can occur using the `State` object after
        # leaving the context.
        state.decommission()

    def set_state_root(self, state_root):
        self.state_root = state_root

    #
    # Access self._chaindb
    #
    def snapshot(self):
        """
        Perform a full snapshot of the current state.

        Snapshots are a combination of the state_root at the time of the
        snapshot and the checkpoint_id returned from the journaled DB.
        """
        return (self.state_root, self._chaindb.snapshot())

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
    # Access self.prev_hashes (Read-only)
    #
    def get_ancestor_hash(self, block_number):
        """
        Return the hash of the ancestor with the given block number.
        """
        ancestor_depth = self.block_number - block_number - 1
        is_ancestor_depth_out_of_range = (
            ancestor_depth >= MAX_PREV_HEADER_DEPTH or
            ancestor_depth < 0 or
            ancestor_depth >= len(self.execution_context.prev_hashes)
        )
        if is_ancestor_depth_out_of_range:
            return b''
        ancestor_hash = self.execution_context.prev_hashes[ancestor_depth]
        return ancestor_hash

    #
    # Computation
    #
    def get_computation(self, message, transaction_context):
        """
        Return state object
        """
        if self.computation_class is None:
            raise AttributeError("No `computation_class` has been set for this VMState")
        else:
            computation = self.computation_class(self, message, transaction_context)
        return computation

    #
    # Transaction context
    #
    @classmethod
    def get_transaction_context_class(cls):
        """

        """
        if cls.transaction_context_class is None:
            raise AttributeError("No `transaction_context_class` has been set for this VMState")
        return cls.transaction_context_class

    #
    # Execution
    #
    def apply_transaction(
            self,
            transaction,
            block):
        """
        Apply transaction to the given block

        :param transaction: the transaction to apply
        :param block: the block which the transaction applies on
        :type transaction: Transaction
        :type block: Block

        :return: the computation, applied block, and the trie_data_dict
        :rtype: (Computation, Block, dict[bytes, bytes])
        """
        # Don't modify the given block
        block.make_immutable()
        self.set_state_root(block.header.state_root)
        computation = self.execute_transaction(transaction)

        # Set block.
        block, trie_data_dict = self.add_transaction(transaction, computation, block)
        block.header.state_root = self.state_root
        return computation, block, trie_data_dict

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

        # Create a new Block object
        block_header = block.header.clone()
        transactions = list(block.transactions)
        block = self.block_class(block_header, transactions)

        block.transactions.append(transaction)

        # Get trie roots and changed key-values.
        tx_root_hash, tx_kv_nodes = make_trie_root_and_nodes(
            block.transactions,
            self.trie_class,
        )
        receipt_root_hash, receipt_kv_nodes = make_trie_root_and_nodes(
            self.receipts,
            self.trie_class,
        )

        trie_data = merge(tx_kv_nodes, receipt_kv_nodes)

        block.bloom_filter |= receipt.bloom

        block.header.transaction_root = tx_root_hash
        block.header.receipt_root = receipt_root_hash
        block.header.bloom = int(block.bloom_filter)
        block.header.gas_used = receipt.gas_used

        return block, trie_data

    def add_receipt(self, receipt):
        self.receipts.append(receipt)

    @abstractmethod
    def make_receipt(self, transaction, computation):
        """
        Make receipt.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    #
    # Finalization
    #
    def finalize_block(self, block):
        """
        Apply rewards.
        """
        block_reward = self.get_block_reward() + (
            len(block.uncles) * self.get_nephew_reward()
        )

        with self.state_db() as state_db:
            state_db.delta_balance(block.header.coinbase, block_reward)
            self.logger.debug(
                "BLOCK REWARD: %s -> %s",
                block_reward,
                block.header.coinbase,
            )

            for uncle in block.uncles:
                uncle_reward = self.get_uncle_reward(block.number, uncle)
                state_db.delta_balance(uncle.coinbase, uncle_reward)
                self.logger.debug(
                    "UNCLE REWARD REWARD: %s -> %s",
                    uncle_reward,
                    uncle.coinbase,
                )
        block.header.state_root = self.state_root
        return block

    @staticmethod
    @abstractmethod
    def get_block_reward():
        raise NotImplementedError("Must be implemented by subclasses")

    @staticmethod
    @abstractmethod
    def get_uncle_reward(block_number, uncle):
        raise NotImplementedError("Must be implemented by subclasses")

    @classmethod
    @abstractmethod
    def get_nephew_reward(cls):
        raise NotImplementedError("Must be implemented by subclasses")


class BaseTransactionExecutor(metaclass=ABCMeta):
    def execute_transaction(self, transaction):
        """
        Execute the transaction in the vm.
        """
        message = self.run_pre_computation(transaction)
        computation = self.run_computation(transaction, message)
        return self.run_post_computation(transaction, computation)

    @abstractmethod
    def run_pre_computation(self, transaction):
        raise NotImplementedError()

    @abstractmethod
    def run_computation(self, transaction, message):
        raise NotImplementedError()

    @abstractmethod
    def run_post_computation(self, transaction, computation):
        raise NotImplementedError()
