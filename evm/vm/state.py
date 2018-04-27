from abc import (
    ABCMeta,
    abstractmethod
)
import logging
from typing import (  # noqa: F401
    Type,
    TYPE_CHECKING
)

from eth_bloom import (
    BloomFilter,
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
from evm.db.journal import (
    JournalDB,
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
    _db = None
    execution_context = None
    state_root = None

    computation_class = None  # type: Type[BaseComputation]
    transaction_context_class = None  # type: Type[BaseTransactionContext]
    account_db_class = None  # Type[BaseAccountDB]

    def __init__(self, db, execution_context, state_root):
        self._db = db
        self._journal_db = JournalDB(self._db)
        self.account_db = self.get_account_db_class()(self._journal_db, state_root)
        self.execution_context = execution_context

    @classmethod
    def get_account_db_class(cls):
        if cls.account_db_class is None:
            raise AttributeError("No account_db_class defined for {0}".format(cls.__name__))
        return cls.account_db_class

    #
    # Account State
    #
    @property
    def state_root(self):
        return self.account_db.root_hash

    def snapshot(self):
        """
        Perform a full snapshot of the current state.

        Snapshots are a combination of the state_root at the time of the
        snapshot and the id of the changeset from the journaled DB.
        """
        return (self.state_root, self._journal_db.record())

    def revert(self, snapshot):
        """
        Revert the VM to the state at the snapshot
        """
        state_root, changeset_id = snapshot

        # roll the underlying database back
        self._journal_db.discard(changeset_id)

        # replace the account_db
        self.account_db = self.get_account_db_class()(self._journal_db, state_root)

    def commit(self, snapshot):
        """
        Commits the journal to the point where the snapshot was taken.  This
        will merge in any changesets that were recorded *after* the snapshot changeset.
        """
        _, checkpoint_id = snapshot
        self._journal_db.commit(checkpoint_id)

    def persist(self):
        self._journal_db.persist()

    def reset(self):
        self._journal_db = JournalDB(self._db)
        self.record()

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
        self.set_state_root(block.header.state_root)
        computation = self.execute_transaction(transaction)

        # Set block.
        new_block, receipt = self.add_transaction(transaction, computation, block)
        return new_block, receipt, computation

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

        new_header = block.header.copy(
            bloom=int(BloomFilter(block.header.bloom) | receipt.bloom),
            gas_used=receipt.gas_used,
            state_root=self.state_root,
        )
        new_block = block.copy(
            header=new_header,
            transactions=tuple(block.transactions) + (transaction,),
        )

        return new_block, receipt

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
