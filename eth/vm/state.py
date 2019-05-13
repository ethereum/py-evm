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
from eth_utils.toolz import nth

from eth.constants import (
    BLANK_ROOT_HASH,
    MAX_PREV_HEADER_DEPTH,
)
from eth.db.account import (  # noqa: F401
    BaseAccountDB,
    AccountDB,
)
from eth.db.backends.base import (
    BaseAtomicDB,
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
    __slots__ = ['_db', 'execution_context', '_account_db']

    computation_class = None  # type: Type[BaseComputation]
    transaction_context_class = None  # type: Type[BaseTransactionContext]
    account_db_class = None  # type: Type[BaseAccountDB]
    transaction_executor = None  # type: Type[BaseTransactionExecutor]

    def __init__(
            self,
            db: BaseAtomicDB,
            execution_context: ExecutionContext,
            state_root: bytes) -> None:
        self._db = db
        self.execution_context = execution_context
        self._account_db = self.get_account_db_class()(db, state_root)

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
    def state_root(self) -> Hash32:
        """
        Return the current ``state_root`` from the underlying database
        """
        return self._account_db.state_root

    def make_state_root(self) -> Hash32:
        return self._account_db.make_state_root()

    def get_storage(self, address: Address, slot: int, from_journal: bool=True) -> int:
        return self._account_db.get_storage(address, slot, from_journal)

    def set_storage(self, address: Address, slot: int, value: int) -> None:
        return self._account_db.set_storage(address, slot, value)

    def delete_storage(self, address: Address) -> None:
        self._account_db.delete_storage(address)

    def delete_account(self, address: Address) -> None:
        self._account_db.delete_account(address)

    def get_balance(self, address: Address) -> int:
        return self._account_db.get_balance(address)

    def set_balance(self, address: Address, balance: int) -> None:
        self._account_db.set_balance(address, balance)

    def delta_balance(self, address: Address, delta: int) -> None:
        self.set_balance(address, self.get_balance(address) + delta)

    def get_nonce(self, address: Address) -> int:
        return self._account_db.get_nonce(address)

    def set_nonce(self, address: Address, nonce: int) -> None:
        self._account_db.set_nonce(address, nonce)

    def increment_nonce(self, address: Address) -> None:
        self._account_db.increment_nonce(address)

    def get_code(self, address: Address) -> bytes:
        return self._account_db.get_code(address)

    def set_code(self, address: Address, code: bytes) -> None:
        self._account_db.set_code(address, code)

    def get_code_hash(self, address: Address) -> Hash32:
        return self._account_db.get_code_hash(address)

    def delete_code(self, address: Address) -> None:
        self._account_db.delete_code(address)

    def has_code_or_nonce(self, address: Address) -> bool:
        return self._account_db.account_has_code_or_nonce(address)

    def account_exists(self, address: Address) -> bool:
        return self._account_db.account_exists(address)

    def touch_account(self, address: Address) -> None:
        self._account_db.touch_account(address)

    def account_is_empty(self, address: Address) -> bool:
        return self._account_db.account_is_empty(address)

    #
    # Access self._chaindb
    #
    def snapshot(self) -> Tuple[Hash32, UUID]:
        """
        Perform a full snapshot of the current state.

        Snapshots are a combination of the :attr:`~state_root` at the time of the
        snapshot and the checkpoint from the journaled DB.
        """
        return self.state_root, self._account_db.record()

    def revert(self, snapshot: Tuple[Hash32, UUID]) -> None:
        """
        Revert the VM to the state at the snapshot
        """
        state_root, account_snapshot = snapshot

        # first revert the database state root.
        self._account_db.state_root = state_root
        # now roll the underlying database back
        self._account_db.discard(account_snapshot)

    def commit(self, snapshot: Tuple[Hash32, UUID]) -> None:
        """
        Commit the journal to the point where the snapshot was taken.  This
        merges in any changes that were recorded since the snapshot.
        """
        _, account_snapshot = snapshot
        self._account_db.commit(account_snapshot)

    def persist(self) -> None:
        self._account_db.persist()

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
            block_number < 0
        )
        if is_ancestor_depth_out_of_range:
            return Hash32(b'')

        try:
            return nth(ancestor_depth, self.execution_context.prev_hashes)
        except StopIteration:
            # Ancestor with specified depth not present
            return Hash32(b'')

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
    def apply_transaction(
            self,
            transaction: BaseOrSpoofTransaction) -> 'BaseComputation':
        """
        Apply transaction to the vm state

        :param transaction: the transaction to apply
        :return: the computation
        """
        if self.state_root != BLANK_ROOT_HASH and not self._account_db.has_root(self.state_root):
            raise StateRootNotFound(self.state_root)
        else:
            return self.execute_transaction(transaction)

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
