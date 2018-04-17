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

from eth_utils import (
    to_bytes
)

from evm.constants import (
    DEFAULT_DO_CALL_R,
    DEFAULT_DO_CALL_S,
    DEFAULT_DO_CALL_SENDER,
    DEFAULT_DO_CALL_V,
    MAX_PREV_HEADER_DEPTH,
    UINT_256_MAX,
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
    from evm.vm.transaction_context import (  # noqa: F401
        BaseTransactionContext,
    )


class BaseState(Configurable, metaclass=ABCMeta):
    #
    # Set from __init__
    #
    _chaindb = None
    execution_context = None
    state_root = None
    gas_used = None

    block_class = None  # type: Type[BaseBlock]
    computation_class = None  # type: Type[BaseComputation]
    trie_class = None
    transaction_context_class = None  # type: Type[BaseTransactionContext]

    def __init__(self, chaindb, execution_context, state_root, gas_used):
        self._chaindb = chaindb
        self.execution_context = execution_context
        self.state_root = state_root
        self.gas_used = gas_used

    #
    # Logging
    #
    @property
    def logger(self):
        return logging.getLogger('evm.vm.state.{0}'.format(self.__class__.__name__))

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
    # read only state_db
    #
    @property
    def read_only_state_db(self):
        return self._chaindb.get_state_db(self.state_root, read_only=True)

    #
    # mutable state_db
    #
    @contextmanager
    def mutable_state_db(self):
        state = self._chaindb.get_state_db(self.state_root, read_only=False)
        yield state

        if self.state_root != state.root_hash:
            self.set_state_root(state.root_hash)

        # remove the reference to the underlying `db` object to ensure that no
        # further modifications can occur using the `State` object after
        # leaving the context.
        state.decommission()

    #
    # state_db
    #
    @contextmanager
    def state_db(self, read_only=False):
        state = self._chaindb.get_state_db(
            self.state_root,
            read_only,
        )
        yield state

        if self.state_root != state.root_hash:
            self.set_state_root(state.root_hash)

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

        with self.mutable_state_db() as state_db:
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
        Return a computation instance for the given `message` and `transaction_context`
        """
        if self.computation_class is None:
            raise AttributeError("No `computation_class` has been set for this State")
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
            raise AttributeError("No `transaction_context_class` has been set for this State")
        return cls.transaction_context_class

    #
    # Block class
    #
    @classmethod
    def get_block_class(cls) -> Type['BaseBlock']:
        """

        """
        if cls.block_class is None:
            raise AttributeError("No `block_class_class` has been set for this VMState")
        return cls.block_class

    #
    # Execution
    #

    def do_call(self, transaction):

        _transaction = transaction

        _transaction.v = DEFAULT_DO_CALL_V
        _transaction.s = DEFAULT_DO_CALL_S
        _transaction.r = DEFAULT_DO_CALL_R

        snapshot = self.snapshot()
        try:
            with self.mutable_state_db() as state_db:

                if not hasattr(_transaction, "get_sender"):
                    _transaction.get_sender = \
                        lambda: to_bytes(hexstr=DEFAULT_DO_CALL_SENDER)
                    _transaction.sender = to_bytes(hexstr=DEFAULT_DO_CALL_SENDER)

                # set the account balance of the sender to an arbitrary large
                # amount to ensure they have the necessary funds to pay for the
                # transaction.
                state_db.set_balance(transaction.sender, UINT_256_MAX // 2)

            computation = self.execute_transaction(_transaction)

        finally:
            self.revert(snapshot)

        return computation

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
        block, receipt = self.add_transaction(transaction, computation, block)
        block.header.state_root = self.state_root
        return computation, block, receipt

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
        self.gas_used = receipt.gas_used

        # Create a new Block object
        block_header = block.header.clone()
        transactions = list(block.transactions)
        block = self.get_block_class()(block_header, transactions)

        block.transactions.append(transaction)

        block.bloom_filter |= receipt.bloom

        block.header.bloom = int(block.bloom_filter)
        block.header.gas_used = receipt.gas_used

        return block, receipt

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

        with self.mutable_state_db() as state_db:
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
