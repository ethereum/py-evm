from abc import (
    ABC,
    abstractmethod
)
import contextlib
import logging
from typing import (  # noqa: F401
    cast,
    Callable,
    Iterator,
    Tuple,
    Type,
    TYPE_CHECKING,
    Union,
)
from uuid import UUID

from eth_typing import (
    Address,
    Hash32,
)

from eth.constants import (
    BLANK_ROOT_HASH,
    MAX_PREV_HEADER_DEPTH,
)
from eth.db.account import (  # noqa: F401
    BaseAccountDB,
    AccountDB,
)
from eth.db.backends.base import (
    BaseDB,
)
from eth.exceptions import StateRootNotFound
from eth.tools.logging import (
    ExtendedDebugLogger,
)
from eth.typing import (
    BaseOrSpoofTransaction,
)
from eth._utils.datatypes import (
    Configurable,
)
from eth.vm.execution_context import (
    ExecutionContext,
)
from eth.vm.message import Message

if TYPE_CHECKING:
    from eth.computation import (  # noqa: F401
        BaseComputation,
    )
    from eth.rlp.transactions import (  # noqa: F401
        BaseTransaction,
    )

    from eth.vm.transaction_context import (  # noqa: F401
        BaseTransactionContext,
    )


class BaseState(Configurable, ABC):
    """
    The base class that encapsulates all of the various moving parts related to
    the state of the VM during execution.
    Each :class:`~eth.vm.base.BaseVM` must be configured with a subclass of the
    :class:`~eth.vm.state.BaseState`.

      .. note::

        Each :class:`~eth.vm.state.BaseState` class must be configured with:

        - ``computation_class``: The :class:`~eth.vm.computation.BaseComputation` class for
          vm execution.
        - ``transaction_context_class``: The :class:`~eth.vm.transaction_context.TransactionContext`
          class for vm execution.
    """
    #
    # Set from __init__
    #
    __slots__ = ['_db', 'execution_context', 'account_db']

    computation_class = None  # type: Type[BaseComputation]
    transaction_context_class = None  # type: Type[BaseTransactionContext]
    account_db_class = None  # type: Type[BaseAccountDB]
    transaction_executor = None  # type: Type[BaseTransactionExecutor]

    def __init__(self, db: BaseDB, execution_context: ExecutionContext, state_root: bytes) -> None:
        self._db = db
        self.execution_context = execution_context
        self.account_db = self.get_account_db_class()(self._db, state_root)

    #
    # Logging
    #
    @property
    def logger(self) -> ExtendedDebugLogger:
        normal_logger = logging.getLogger('eth.vm.state.{0}'.format(self.__class__.__name__))
        return cast(ExtendedDebugLogger, normal_logger)

    #
    # Block Object Properties (in opcodes)
    #

    @property
    def coinbase(self) -> Address:
        """
        Return the current ``coinbase`` from the current :attr:`~execution_context`
        """
        return self.execution_context.coinbase

    @property
    def timestamp(self) -> int:
        """
        Return the current ``timestamp`` from the current :attr:`~execution_context`
        """
        return self.execution_context.timestamp

    @property
    def block_number(self) -> int:
        """
        Return the current ``block_number`` from the current :attr:`~execution_context`
        """
        return self.execution_context.block_number

    @property
    def difficulty(self) -> int:
        """
        Return the current ``difficulty`` from the current :attr:`~execution_context`
        """
        return self.execution_context.difficulty

    @property
    def gas_limit(self) -> int:
        """
        Return the current ``gas_limit`` from the current :attr:`~transaction_context`
        """
        return self.execution_context.gas_limit

    #
    # Access to account db
    #
    @classmethod
    def get_account_db_class(cls) -> Type[BaseAccountDB]:
        """
        Return the :class:`~eth.db.account.BaseAccountDB` class that the
        state class uses.
        """
        if cls.account_db_class is None:
            raise AttributeError("No account_db_class set for {0}".format(cls.__name__))
        return cls.account_db_class

    @property
    def state_root(self) -> bytes:
        """
        Return the current ``state_root`` from the underlying database
        """
        return self.account_db.state_root

    #
    # Access self._chaindb
    #
    def snapshot(self) -> Tuple[bytes, Tuple[UUID, UUID]]:
        """
        Perform a full snapshot of the current state.

        Snapshots are a combination of the :attr:`~state_root` at the time of the
        snapshot and the id of the changeset from the journaled DB.
        """
        return (self.state_root, self.account_db.record())

    def revert(self, snapshot: Tuple[bytes, Tuple[UUID, UUID]]) -> None:
        """
        Revert the VM to the state at the snapshot
        """
        state_root, changeset_id = snapshot

        # first revert the database state root.
        self.account_db.state_root = state_root
        # now roll the underlying database back
        self.account_db.discard(changeset_id)

    def commit(self, snapshot: Tuple[bytes, Tuple[UUID, UUID]]) -> None:
        """
        Commit the journal to the point where the snapshot was taken.  This
        will merge in any changesets that were recorded *after* the snapshot changeset.
        """
        _, checkpoint_id = snapshot
        self.account_db.commit(checkpoint_id)

    #
    # Access self.prev_hashes (Read-only)
    #
    def get_ancestor_hash(self, block_number: int) -> Hash32:
        """
        Return the hash for the ancestor block with number ``block_number``.
        Return the empty bytestring ``b''`` if the block number is outside of the
        range of available block numbers (typically the last 255 blocks).
        """
        ancestor_depth = self.block_number - block_number - 1
        is_ancestor_depth_out_of_range = (
            ancestor_depth >= MAX_PREV_HEADER_DEPTH or
            ancestor_depth < 0 or
            ancestor_depth >= len(self.execution_context.prev_hashes)
        )
        if is_ancestor_depth_out_of_range:
            return Hash32(b'')
        ancestor_hash = self.execution_context.prev_hashes[ancestor_depth]
        return ancestor_hash

    #
    # Computation
    #
    def get_computation(self,
                        message: Message,
                        transaction_context: 'BaseTransactionContext') -> 'BaseComputation':
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
    def get_transaction_context_class(cls) -> Type['BaseTransactionContext']:
        """
        Return the :class:`~eth.vm.transaction_context.BaseTransactionContext` class that the
        state class uses.
        """
        if cls.transaction_context_class is None:
            raise AttributeError("No `transaction_context_class` has been set for this State")
        return cls.transaction_context_class

    #
    # Execution
    #
    def apply_transaction(self, transaction: 'BaseTransaction') -> Tuple[bytes, 'BaseComputation']:
        """
        Apply transaction to the vm state

        :param transaction: the transaction to apply
        :return: the new state root, and the computation
        """
        if self.state_root != BLANK_ROOT_HASH and not self.account_db.has_root(self.state_root):
            raise StateRootNotFound(self.state_root)
        computation = self.execute_transaction(transaction)
        state_root = self.account_db.make_state_root()
        return state_root, computation

    def get_transaction_executor(self) -> 'BaseTransactionExecutor':
        return self.transaction_executor(self)

    def costless_execute_transaction(self,
                                     transaction: BaseOrSpoofTransaction) -> 'BaseComputation':
        with self.override_transaction_context(gas_price=transaction.gas_price):
            free_transaction = transaction.copy(gas_price=0)
            return self.execute_transaction(free_transaction)

    @contextlib.contextmanager
    def override_transaction_context(self, gas_price: int) -> Iterator[None]:
        original_context = self.get_transaction_context

        def get_custom_transaction_context(transaction: 'BaseTransaction') -> 'BaseTransactionContext':   # noqa: E501
            custom_transaction = transaction.copy(gas_price=gas_price)
            return original_context(custom_transaction)

        self.get_transaction_context = get_custom_transaction_context
        try:
            yield
        finally:
            self.get_transaction_context = original_context     # type: ignore # Remove ignore if https://github.com/python/mypy/issues/708 is fixed. # noqa: E501

    @abstractmethod
    def execute_transaction(self, transaction: BaseOrSpoofTransaction) -> 'BaseComputation':
        raise NotImplementedError()

    @abstractmethod
    def validate_transaction(self, transaction: BaseOrSpoofTransaction) -> None:
        raise NotImplementedError

    @classmethod
    def get_transaction_context(cls,
                                transaction: BaseOrSpoofTransaction) -> 'BaseTransactionContext':
        return cls.get_transaction_context_class()(
            gas_price=transaction.gas_price,
            origin=transaction.sender,
        )


class BaseTransactionExecutor(ABC):
    def __init__(self, vm_state: BaseState) -> None:
        self.vm_state = vm_state

    def __call__(self, transaction: BaseOrSpoofTransaction) -> 'BaseComputation':
        valid_transaction = self.validate_transaction(transaction)
        message = self.build_evm_message(valid_transaction)
        computation = self.build_computation(message, valid_transaction)
        finalized_computation = self.finalize_computation(valid_transaction, computation)
        return finalized_computation

    @abstractmethod
    def validate_transaction(self, transaction: BaseOrSpoofTransaction) -> BaseOrSpoofTransaction:
        raise NotImplementedError

    @abstractmethod
    def build_evm_message(self, transaction: BaseOrSpoofTransaction) -> Message:
        raise NotImplementedError()

    @abstractmethod
    def build_computation(self,
                          message: Message,
                          transaction: BaseOrSpoofTransaction) -> 'BaseComputation':
        raise NotImplementedError()

    @abstractmethod
    def finalize_computation(self,
                             transaction: BaseOrSpoofTransaction,
                             computation: 'BaseComputation') -> 'BaseComputation':
        raise NotImplementedError()
