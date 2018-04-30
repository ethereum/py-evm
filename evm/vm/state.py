from abc import (
    ABCMeta,
    abstractmethod
)
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
from evm.db.account import (  # noqa: F401
    BaseAccountDB,
    AccountDB,
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
    transaction_context_class = None  # type: Type[BaseTransactionContext]
    account_db_class = None  # type: Type[BaseAccountDB]

    def __init__(self, db, execution_context, state_root, gas_used):
        self._db = db
        self.execution_context = execution_context
        self.account_db = self.get_account_db_class()(self._db, state_root)
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
    # Access to account db
    #
    @classmethod
    def get_account_db_class(cls):
        if cls.account_db_class is None:
            raise AttributeError("No account_db_class set for {0}".format(cls.__name__))
        return cls.account_db_class

    @property
    def state_root(self):
        return self.account_db.state_root

    #
    # Access self._chaindb
    #
    def snapshot(self):
        """
        Perform a full snapshot of the current state.

        Snapshots are a combination of the state_root at the time of the
        snapshot and the id of the changeset from the journaled DB.
        """
        return (self.state_root, self.account_db.record())

    def revert(self, snapshot):
        """
        Revert the VM to the state at the snapshot
        """
        state_root, changeset_id = snapshot

        # first revert the database state root.
        self.account_db.state_root = state_root
        # now roll the underlying database back
        self.account_db.discard(changeset_id)

    def commit(self, snapshot):
        """
        Commits the journal to the point where the snapshot was taken.  This
        will merge in any changesets that were recorded *after* the snapshot changeset.
        """
        _, checkpoint_id = snapshot
        self.account_db.commit(checkpoint_id)

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
        Return the class used for Blocks

        TODO: this should move up to the VM
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
            if not hasattr(_transaction, "get_sender"):
                _transaction.get_sender = \
                    lambda: to_bytes(hexstr=DEFAULT_DO_CALL_SENDER)
                _transaction.sender = to_bytes(hexstr=DEFAULT_DO_CALL_SENDER)

            # set the account balance of the sender to an arbitrary large
            # amount to ensure they have the necessary funds to pay for the
            # transaction.
            self.account_db.set_balance(transaction.sender, UINT_256_MAX // 2)

            computation = self.execute_transaction(_transaction)

        finally:
            self.revert(snapshot)

        return computation

    def apply_transaction(
            self,
            transaction):
        """
        Apply transaction to the vm state

        :param transaction: the transaction to apply
        :type transaction: Transaction

        :return: the computation, applied block, and the trie_data_dict
        :rtype: (Computation, dict[bytes, bytes])
        """
        computation = self.execute_transaction(transaction)
        self.account_db.persist()
        return self.account_db.state_root, computation

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

        self.account_db.delta_balance(block.header.coinbase, block_reward)
        self.logger.debug(
            "BLOCK REWARD: %s -> %s",
            block_reward,
            block.header.coinbase,
        )

        for uncle in block.uncles:
            uncle_reward = self.get_uncle_reward(block.number, uncle)
            self.account_db.delta_balance(uncle.coinbase, uncle_reward)
            self.logger.debug(
                "UNCLE REWARD REWARD: %s -> %s",
                uncle_reward,
                uncle.coinbase,
            )
        # We need to call `persist` here since the state db batches
        # all writes untill we tell it to write to the underlying db
        # TODO: Refactor to only use batching/journaling for tx processing
        self.account_db.persist()

        return block.copy(header=block.header.copy(state_root=self.state_root))

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
