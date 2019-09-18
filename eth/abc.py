from abc import (
    ABC,
    abstractmethod
)
from typing import (
    Any,
    Callable,
    ContextManager,
    Dict,
    Iterable,
    Iterator,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
)
from uuid import UUID

import rlp

from eth_bloom import BloomFilter

from eth_typing import (
    Address,
    BlockNumber,
    Hash32,
)

from eth_utils import ExtendedDebugLogger

from eth_keys.datatypes import PrivateKey

from eth.constants import (
    BLANK_ROOT_HASH,
)
from eth.exceptions import VMError
from eth.typing import (
    BytesOrView,
    JournalDBCheckpoint,
    AccountState,
    HeaderParams,
)


T = TypeVar('T')


class MiningHeaderAPI(rlp.Serializable, ABC):
    parent_hash: Hash32
    uncles_hash: Hash32
    coinbase: Address
    state_root: Hash32
    transaction_root: Hash32
    receipt_root: Hash32
    bloom: int
    difficulty: int
    block_number: BlockNumber
    gas_limit: int
    gas_used: int
    timestamp: int
    extra_data: bytes


class BlockHeaderAPI(MiningHeaderAPI):
    mix_hash: Hash32
    nonce: bytes


class LogAPI(rlp.Serializable, ABC):
    address: Address
    topics: Sequence[int]
    data: bytes

    @property
    @abstractmethod
    def bloomables(self) -> Tuple[bytes, ...]:
        ...


class ReceiptAPI(rlp.Serializable, ABC):
    state_root: bytes
    gas_used: int
    bloom: int
    logs: Sequence[LogAPI]

    @property
    @abstractmethod
    def bloom_filter(self) -> BloomFilter:
        ...


class BaseTransactionAPI(ABC):
    @abstractmethod
    def validate(self) -> None:
        ...

    @property
    @abstractmethod
    def intrinsic_gas(self) -> int:
        ...

    @abstractmethod
    def get_intrinsic_gas(self) -> int:
        ...

    @abstractmethod
    def gas_used_by(self, computation: 'ComputationAPI') -> int:
        ...

    @abstractmethod
    def copy(self: T, **overrides: Any) -> T:
        ...


class TransactionFieldsAPI(ABC):
    nonce: int
    gas_price: int
    gas: int
    to: Address
    value: int
    data: bytes
    v: int
    r: int
    s: int

    @property
    @abstractmethod
    def hash(self) -> bytes:
        ...


class UnsignedTransactionAPI(rlp.Serializable, BaseTransactionAPI):
    nonce: int
    gas_price: int
    gas: int
    to: Address
    value: int
    data: bytes

    #
    # API that must be implemented by all Transaction subclasses.
    #
    @abstractmethod
    def as_signed_transaction(self, private_key: PrivateKey) -> 'SignedTransactionAPI':
        """
        Return a version of this transaction which has been signed using the
        provided `private_key`
        """
        ...


class SignedTransactionAPI(rlp.Serializable, BaseTransactionAPI, TransactionFieldsAPI):
    @classmethod
    @abstractmethod
    def from_base_transaction(cls, transaction: 'SignedTransactionAPI') -> 'SignedTransactionAPI':
        ...

    @property
    @abstractmethod
    def sender(self) -> Address:
        ...

    # +-------------------------------------------------------------+
    # | API that must be implemented by all Transaction subclasses. |
    # +-------------------------------------------------------------+

    #
    # Validation
    #
    @abstractmethod
    def validate(self) -> None:
        ...

    #
    # Signature and Sender
    #
    @property
    @abstractmethod
    def is_signature_valid(self) -> bool:
        ...

    @abstractmethod
    def check_signature_validity(self) -> None:
        """
        Checks signature validity, raising a ValidationError if the signature
        is invalid.
        """
        ...

    @abstractmethod
    def get_sender(self) -> Address:
        """
        Get the 20-byte address which sent this transaction.

        This can be a slow operation. ``transaction.sender`` is always preferred.
        """
        ...

    #
    # Conversion to and creation of unsigned transactions.
    #
    @abstractmethod
    def get_message_for_signing(self) -> bytes:
        """
        Return the bytestring that should be signed in order to create a signed transactions
        """
        ...

    @classmethod
    @abstractmethod
    def create_unsigned_transaction(cls,
                                    *,
                                    nonce: int,
                                    gas_price: int,
                                    gas: int,
                                    to: Address,
                                    value: int,
                                    data: bytes) -> UnsignedTransactionAPI:
        """
        Create an unsigned transaction.
        """
        ...


class BlockAPI(rlp.Serializable, ABC):
    transaction_class: Type[SignedTransactionAPI] = None

    @classmethod
    @abstractmethod
    def get_transaction_class(cls) -> Type[SignedTransactionAPI]:
        ...

    @classmethod
    @abstractmethod
    def from_header(cls, header: BlockHeaderAPI, chaindb: 'ChainDatabaseAPI') -> 'BlockAPI':
        ...

    @property
    @abstractmethod
    def hash(self) -> Hash32:
        ...

    @property
    @abstractmethod
    def number(self) -> BlockNumber:
        ...

    @property
    @abstractmethod
    def is_genesis(self) -> bool:
        ...


class DatabaseAPI(MutableMapping[bytes, bytes], ABC):
    @abstractmethod
    def set(self, key: bytes, value: bytes) -> None:
        ...

    @abstractmethod
    def exists(self, key: bytes) -> bool:
        ...

    @abstractmethod
    def delete(self, key: bytes) -> None:
        ...


class AtomicDatabaseAPI(DatabaseAPI):
    @abstractmethod
    def atomic_batch(self) -> ContextManager[DatabaseAPI]:
        ...


class HeaderDatabaseAPI(ABC):
    db: AtomicDatabaseAPI

    @abstractmethod
    def __init__(self, db: AtomicDatabaseAPI) -> None:
        ...

    #
    # Canonical Chain API
    #
    @abstractmethod
    def get_canonical_block_hash(self, block_number: BlockNumber) -> Hash32:
        ...

    @abstractmethod
    def get_canonical_block_header_by_number(self, block_number: BlockNumber) -> BlockHeaderAPI:
        ...

    @abstractmethod
    def get_canonical_head(self) -> BlockHeaderAPI:
        ...

    #
    # Header API
    #
    @abstractmethod
    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeaderAPI:
        ...

    @abstractmethod
    def get_score(self, block_hash: Hash32) -> int:
        ...

    @abstractmethod
    def header_exists(self, block_hash: Hash32) -> bool:
        ...

    @abstractmethod
    def persist_checkpoint_header(self, header: BlockHeaderAPI, score: int) -> None:
        ...

    @abstractmethod
    def persist_header(self,
                       header: BlockHeaderAPI
                       ) -> Tuple[Tuple[BlockHeaderAPI, ...], Tuple[BlockHeaderAPI, ...]]:
        ...

    @abstractmethod
    def persist_header_chain(self,
                             headers: Sequence[BlockHeaderAPI],
                             genesis_parent_hash: Hash32 = None,
                             ) -> Tuple[Tuple[BlockHeaderAPI, ...], Tuple[BlockHeaderAPI, ...]]:
        ...


class ChainDatabaseAPI(HeaderDatabaseAPI):
    #
    # Header API
    #
    @abstractmethod
    def get_block_uncles(self, uncles_hash: Hash32) -> Tuple[BlockHeaderAPI, ...]:
        ...

    #
    # Block API
    #
    @abstractmethod
    def persist_block(self,
                      block: BlockAPI,
                      genesis_parent_hash: Hash32 = None,
                      ) -> Tuple[Tuple[Hash32, ...], Tuple[Hash32, ...]]:
        ...

    @abstractmethod
    def persist_uncles(self, uncles: Tuple[BlockHeaderAPI]) -> Hash32:
        ...

    #
    # Transaction API
    #
    @abstractmethod
    def add_receipt(self,
                    block_header: BlockHeaderAPI,
                    index_key: int, receipt: ReceiptAPI) -> Hash32:
        ...

    @abstractmethod
    def add_transaction(self,
                        block_header: BlockHeaderAPI,
                        index_key: int, transaction: SignedTransactionAPI) -> Hash32:
        ...

    @abstractmethod
    def get_block_transactions(
            self,
            block_header: BlockHeaderAPI,
            transaction_class: Type[SignedTransactionAPI]) -> Sequence[SignedTransactionAPI]:
        ...

    @abstractmethod
    def get_block_transaction_hashes(self, block_header: BlockHeaderAPI) -> Tuple[Hash32, ...]:
        ...

    @abstractmethod
    def get_receipt_by_index(self,
                             block_number: BlockNumber,
                             receipt_index: int) -> ReceiptAPI:
        ...

    @abstractmethod
    def get_receipts(self,
                     header: BlockHeaderAPI,
                     receipt_class: Type[ReceiptAPI]) -> Tuple[ReceiptAPI, ...]:
        ...

    @abstractmethod
    def get_transaction_by_index(
            self,
            block_number: BlockNumber,
            transaction_index: int,
            transaction_class: Type[SignedTransactionAPI]) -> SignedTransactionAPI:
        ...

    @abstractmethod
    def get_transaction_index(self, transaction_hash: Hash32) -> Tuple[BlockNumber, int]:
        ...

    #
    # Raw Database API
    #
    @abstractmethod
    def exists(self, key: bytes) -> bool:
        ...

    @abstractmethod
    def get(self, key: bytes) -> bytes:
        ...

    @abstractmethod
    def persist_trie_data_dict(self, trie_data_dict: Dict[Hash32, bytes]) -> None:
        ...


class GasMeterAPI(ABC):
    gas_refunded: int
    gas_remaining: int

    #
    # Write API
    #
    @abstractmethod
    def consume_gas(self, amount: int, reason: str) -> None:
        ...

    @abstractmethod
    def return_gas(self, amount: int) -> None:
        ...

    @abstractmethod
    def refund_gas(self, amount: int) -> None:
        ...


class MessageAPI(ABC):
    """
    A message for VM computation.
    """
    code: bytes
    _code_address: Address
    create_address: Address
    data: BytesOrView
    depth: int
    gas: int
    is_static: bool
    sender: Address
    should_transfer_value: bool
    _storage_address: Address
    to: Address
    value: int

    __slots__ = [
        'code',
        '_code_address',
        'create_address',
        'data',
        'depth',
        'gas',
        'is_static',
        'sender',
        'should_transfer_value',
        '_storage_address'
        'to',
        'value',
    ]

    @property
    @abstractmethod
    def code_address(self) -> Address:
        ...

    @property
    @abstractmethod
    def storage_address(self) -> Address:
        ...

    @property
    @abstractmethod
    def is_create(self) -> bool:
        ...

    @property
    @abstractmethod
    def data_as_bytes(self) -> bytes:
        ...


class OpcodeAPI(ABC):
    mnemonic: str

    @abstractmethod
    def __call__(self, computation: 'ComputationAPI') -> None:
        ...

    @classmethod
    @abstractmethod
    def as_opcode(cls: Type[T],
                  logic_fn: Callable[['ComputationAPI'], None],
                  mnemonic: str,
                  gas_cost: int) -> Type[T]:
        ...

    @abstractmethod
    def __copy__(self) -> 'OpcodeAPI':
        ...

    @abstractmethod
    def __deepcopy__(self, memo: Any) -> 'OpcodeAPI':
        ...


class ChainContextAPI(ABC):
    @abstractmethod
    def __init__(self, chain_id: Optional[int]) -> None:
        ...

    @property
    @abstractmethod
    def chain_id(self) -> int:
        ...


class TransactionContextAPI(ABC):
    @abstractmethod
    def __init__(self, gas_price: int, origin: Address) -> None:
        ...

    @abstractmethod
    def get_next_log_counter(self) -> int:
        ...

    @property
    @abstractmethod
    def gas_price(self) -> int:
        ...

    @property
    @abstractmethod
    def origin(self) -> Address:
        ...


class MemoryAPI(ABC):
    @abstractmethod
    def extend(self, start_position: int, size: int) -> None:
        ...

    @abstractmethod
    def __len__(self) -> int:
        ...

    @abstractmethod
    def write(self, start_position: int, size: int, value: bytes) -> None:
        ...

    @abstractmethod
    def read(self, start_position: int, size: int) -> memoryview:
        ...

    @abstractmethod
    def read_bytes(self, start_position: int, size: int) -> bytes:
        ...


class StackAPI(ABC):
    @abstractmethod
    def push_int(self, value: int) -> None:
        ...

    @abstractmethod
    def push_bytes(self, value: bytes) -> None:
        ...

    @abstractmethod
    def pop1_bytes(self) -> bytes:
        ...

    @abstractmethod
    def pop1_int(self) -> int:
        ...

    @abstractmethod
    def pop1_any(self) -> Union[int, bytes]:
        ...

    @abstractmethod
    def pop_any(self, num_items: int) -> Tuple[Union[int, bytes], ...]:
        ...

    @abstractmethod
    def pop_ints(self, num_items: int) -> Tuple[int, ...]:
        ...

    @abstractmethod
    def pop_bytes(self, num_items: int) -> Tuple[bytes, ...]:
        ...

    @abstractmethod
    def swap(self, position: int) -> None:
        ...

    @abstractmethod
    def dup(self, position: int) -> None:
        ...


class CodeStreamAPI(ABC):
    pc: int

    @abstractmethod
    def read(self, size: int) -> bytes:
        ...

    @abstractmethod
    def __len__(self) -> int:
        ...

    @abstractmethod
    def __getitem__(self, i: int) -> int:
        ...

    @abstractmethod
    def __iter__(self) -> Iterator[int]:
        ...

    @abstractmethod
    def peek(self) -> int:
        ...

    @abstractmethod
    def seek(self, pc: int) -> ContextManager['CodeStreamAPI']:
        ...

    @abstractmethod
    def is_valid_opcode(self, position: int) -> bool:
        ...


class StackManipulationAPI(ABC):
    @abstractmethod
    def stack_pop_ints(self, num_items: int) -> Tuple[int, ...]:
        ...

    @abstractmethod
    def stack_pop_bytes(self, num_items: int) -> Tuple[bytes, ...]:
        ...

    @abstractmethod
    def stack_pop_any(self, num_items: int) -> Tuple[Union[int, bytes], ...]:
        ...

    @abstractmethod
    def stack_pop1_int(self) -> int:
        ...

    @abstractmethod
    def stack_pop1_bytes(self) -> bytes:
        ...

    @abstractmethod
    def stack_pop1_any(self) -> Union[int, bytes]:
        ...

    @abstractmethod
    def stack_push_int(self, value: int) -> None:
        ...

    @abstractmethod
    def stack_push_bytes(self, value: bytes) -> None:
        ...


class ExecutionContextAPI(ABC):
    coinbase: Address
    timestamp: int
    block_number: BlockNumber
    difficulty: int
    gas_limit: int
    prev_hashes: Sequence[Hash32]
    chain_id: int


class ComputationAPI(ContextManager['ComputationAPI'], StackManipulationAPI):
    msg: MessageAPI
    logger: ExtendedDebugLogger
    code: CodeStreamAPI
    opcodes: Dict[int, OpcodeAPI] = None
    state: 'StateAPI'
    return_data: bytes

    @abstractmethod
    def __init__(self,
                 state: 'StateAPI',
                 message: MessageAPI,
                 transaction_context: TransactionContextAPI) -> None:
        ...

    #
    # Convenience
    #
    @property
    @abstractmethod
    def is_origin_computation(self) -> bool:
        ...

    #
    # Error handling
    #
    @property
    @abstractmethod
    def is_success(self) -> bool:
        ...

    @property
    @abstractmethod
    def is_error(self) -> bool:
        ...

    @property
    @abstractmethod
    def error(self) -> VMError:
        ...

    @error.setter
    def error(self, value: VMError) -> None:
        # See: https://github.com/python/mypy/issues/4165
        # Since we can't also decorate this with abstract method we want to be
        # sure that the setter doesn't actually get used as a noop.
        raise NotImplementedError

    @abstractmethod
    def raise_if_error(self) -> None:
        ...

    @property
    @abstractmethod
    def should_burn_gas(self) -> bool:
        ...

    @property
    @abstractmethod
    def should_return_gas(self) -> bool:
        ...

    @property
    @abstractmethod
    def should_erase_return_data(self) -> bool:
        ...

    #
    # Memory Management
    #
    @abstractmethod
    def extend_memory(self, start_position: int, size: int) -> None:
        ...

    @abstractmethod
    def memory_write(self, start_position: int, size: int, value: bytes) -> None:
        ...

    @abstractmethod
    def memory_read(self, start_position: int, size: int) -> memoryview:
        ...

    @abstractmethod
    def memory_read_bytes(self, start_position: int, size: int) -> bytes:
        ...

    #
    # Gas Consumption
    #
    @abstractmethod
    def get_gas_meter(self) -> GasMeterAPI:
        ...

    @abstractmethod
    def consume_gas(self, amount: int, reason: str) -> None:
        ...

    @abstractmethod
    def return_gas(self, amount: int) -> None:
        ...

    @abstractmethod
    def refund_gas(self, amount: int) -> None:
        ...

    @abstractmethod
    def get_gas_refund(self) -> int:
        ...

    @abstractmethod
    def get_gas_used(self) -> int:
        ...

    @abstractmethod
    def get_gas_remaining(self) -> int:
        ...

    #
    # Stack management
    #
    @abstractmethod
    def stack_swap(self, position: int) -> None:
        ...

    @abstractmethod
    def stack_dup(self, position: int) -> None:
        ...

    #
    # Computation result
    #
    @property
    @abstractmethod
    def output(self) -> bytes:
        ...

    @output.setter
    def output(self, value: bytes) -> None:
        # See: https://github.com/python/mypy/issues/4165
        # Since we can't also decorate this with abstract method we want to be
        # sure that the setter doesn't actually get used as a noop.
        raise NotImplementedError

    #
    # Runtime operations
    #
    @abstractmethod
    def prepare_child_message(self,
                              gas: int,
                              to: Address,
                              value: int,
                              data: BytesOrView,
                              code: bytes,
                              **kwargs: Any) -> MessageAPI:
        ...

    @abstractmethod
    def apply_child_computation(self, child_msg: MessageAPI) -> 'ComputationAPI':
        ...

    @abstractmethod
    def generate_child_computation(self, child_msg: MessageAPI) -> 'ComputationAPI':
        ...

    @abstractmethod
    def add_child_computation(self, child_computation: 'ComputationAPI') -> None:
        ...

    #
    # Account management
    #
    @abstractmethod
    def register_account_for_deletion(self, beneficiary: Address) -> None:
        ...

    @abstractmethod
    def get_accounts_for_deletion(self) -> Tuple[Tuple[Address, Address], ...]:
        ...

    #
    # EVM logging
    #
    @abstractmethod
    def add_log_entry(self, account: Address, topics: Tuple[int, ...], data: bytes) -> None:
        ...

    @abstractmethod
    def get_raw_log_entries(self) -> Tuple[Tuple[int, bytes, Tuple[int, ...], bytes], ...]:
        ...

    @abstractmethod
    def get_log_entries(self) -> Tuple[Tuple[bytes, Tuple[int, ...], bytes], ...]:
        ...

    #
    # State Transition
    #
    @abstractmethod
    def apply_message(self) -> 'ComputationAPI':
        ...

    @abstractmethod
    def apply_create_message(self) -> 'ComputationAPI':
        ...

    @classmethod
    @abstractmethod
    def apply_computation(cls,
                          state: 'StateAPI',
                          message: MessageAPI,
                          transaction_context: TransactionContextAPI) -> 'ComputationAPI':
        ...

    #
    # Opcode API
    #
    @property
    @abstractmethod
    def precompiles(self) -> Dict[Address, Callable[['ComputationAPI'], None]]:
        ...

    @abstractmethod
    def get_opcode_fn(self, opcode: int) -> OpcodeAPI:
        ...


class AccountStorageDatabaseAPI(ABC):
    @abstractmethod
    def get(self, slot: int, from_journal: bool=True) -> int:
        ...

    @abstractmethod
    def set(self, slot: int, value: int) -> None:
        ...

    @abstractmethod
    def delete(self) -> None:
        ...

    @abstractmethod
    def record(self, checkpoint: JournalDBCheckpoint) -> None:
        ...

    @abstractmethod
    def discard(self, checkpoint: JournalDBCheckpoint) -> None:
        ...

    @abstractmethod
    def commit(self, checkpoint: JournalDBCheckpoint) -> None:
        ...

    @abstractmethod
    def make_storage_root(self) -> None:
        ...

    @property
    @abstractmethod
    def has_changed_root(self) -> bool:
        ...

    @abstractmethod
    def get_changed_root(self) -> Hash32:
        ...

    @abstractmethod
    def persist(self, db: DatabaseAPI) -> None:
        ...


class AccountDatabaseAPI(ABC):
    @abstractmethod
    def __init__(self, db: AtomicDatabaseAPI, state_root: Hash32 = BLANK_ROOT_HASH) -> None:
        ...

    @property
    @abstractmethod
    def state_root(self) -> Hash32:
        ...

    @abstractmethod
    def has_root(self, state_root: bytes) -> bool:
        ...

    #
    # Storage
    #
    @abstractmethod
    def get_storage(self, address: Address, slot: int, from_journal: bool=True) -> int:
        ...

    @abstractmethod
    def set_storage(self, address: Address, slot: int, value: int) -> None:
        ...

    @abstractmethod
    def delete_storage(self, address: Address) -> None:
        ...

    #
    # Balance
    #
    @abstractmethod
    def get_balance(self, address: Address) -> int:
        ...

    @abstractmethod
    def set_balance(self, address: Address, balance: int) -> None:
        ...

    #
    # Nonce
    #
    @abstractmethod
    def get_nonce(self, address: Address) -> int:
        ...

    @abstractmethod
    def set_nonce(self, address: Address, nonce: int) -> None:
        ...

    @abstractmethod
    def increment_nonce(self, address: Address) -> None:
        ...

    #
    # Code
    #
    @abstractmethod
    def set_code(self, address: Address, code: bytes) -> None:
        ...

    @abstractmethod
    def get_code(self, address: Address) -> bytes:
        ...

    @abstractmethod
    def get_code_hash(self, address: Address) -> Hash32:
        ...

    @abstractmethod
    def delete_code(self, address: Address) -> None:
        ...

    #
    # Account Methods
    #
    @abstractmethod
    def account_has_code_or_nonce(self, address: Address) -> bool:
        ...

    @abstractmethod
    def delete_account(self, address: Address) -> None:
        ...

    @abstractmethod
    def account_exists(self, address: Address) -> bool:
        ...

    @abstractmethod
    def touch_account(self, address: Address) -> None:
        ...

    @abstractmethod
    def account_is_empty(self, address: Address) -> bool:
        ...

    #
    # Record and discard API
    #
    @abstractmethod
    def record(self) -> JournalDBCheckpoint:
        ...

    @abstractmethod
    def discard(self, checkpoint: JournalDBCheckpoint) -> None:
        ...

    @abstractmethod
    def commit(self, checkpoint: JournalDBCheckpoint) -> None:
        ...

    @abstractmethod
    def make_state_root(self) -> Hash32:
        """
        Generate the state root with all the current changes in AccountDB

        Current changes include every pending change to storage, as well as all account changes.
        After generating all the required tries, the final account state root is returned.

        This is an expensive operation, so should be called as little as possible. For example,
        pre-Byzantium, this is called after every transaction, because we need the state root
        in each receipt. Byzantium+, we only need state roots at the end of the block,
        so we *only* call it right before persistance.

        :return: the new state root
        """
        ...

    @abstractmethod
    def persist(self) -> None:
        """
        Send changes to underlying database, including the trie state
        so that it will forever be possible to read the trie from this checkpoint.

        :meth:`make_state_root` must be explicitly called before this method.
        Otherwise persist will raise a ValidationError.
        """
        ...


class TransactionExecutorAPI(ABC):
    @abstractmethod
    def __init__(self, vm_state: 'StateAPI') -> None:
        ...

    @abstractmethod
    def __call__(self, transaction: SignedTransactionAPI) -> 'ComputationAPI':
        ...

    @abstractmethod
    def validate_transaction(self, transaction: SignedTransactionAPI) -> None:
        ...

    @abstractmethod
    def build_evm_message(self, transaction: SignedTransactionAPI) -> MessageAPI:
        ...

    @abstractmethod
    def build_computation(self,
                          message: MessageAPI,
                          transaction: SignedTransactionAPI) -> 'ComputationAPI':
        ...

    @abstractmethod
    def finalize_computation(self,
                             transaction: SignedTransactionAPI,
                             computation: 'ComputationAPI') -> 'ComputationAPI':
        ...


class ConfigurableAPI(ABC):
    @classmethod
    @abstractmethod
    def configure(cls: Type[T],
                  __name__: str=None,
                  **overrides: Any) -> Type[T]:
        ...


class StateAPI(ConfigurableAPI):
    #
    # Set from __init__
    #
    execution_context: ExecutionContextAPI

    computation_class: Type[ComputationAPI]
    transaction_context_class: Type[TransactionContextAPI]
    account_db_class: Type[AccountDatabaseAPI]
    transaction_executor_class: Type[TransactionExecutorAPI] = None

    @abstractmethod
    def __init__(
            self,
            db: AtomicDatabaseAPI,
            execution_context: ExecutionContextAPI,
            state_root: bytes) -> None:
        ...

    @property
    @abstractmethod
    def logger(self) -> ExtendedDebugLogger:
        ...

    #
    # Block Object Properties (in opcodes)
    #
    @property
    @abstractmethod
    def coinbase(self) -> Address:
        ...

    @property
    @abstractmethod
    def timestamp(self) -> int:
        ...

    @property
    @abstractmethod
    def block_number(self) -> BlockNumber:
        ...

    @property
    @abstractmethod
    def difficulty(self) -> int:
        ...

    @property
    @abstractmethod
    def gas_limit(self) -> int:
        ...

    #
    # Access to account db
    #
    @classmethod
    @abstractmethod
    def get_account_db_class(cls) -> Type[AccountDatabaseAPI]:
        ...

    @property
    @abstractmethod
    def state_root(self) -> Hash32:
        ...

    @abstractmethod
    def make_state_root(self) -> Hash32:
        ...

    @abstractmethod
    def get_storage(self, address: Address, slot: int, from_journal: bool=True) -> int:
        ...

    @abstractmethod
    def set_storage(self, address: Address, slot: int, value: int) -> None:
        ...

    @abstractmethod
    def delete_storage(self, address: Address) -> None:
        ...

    @abstractmethod
    def delete_account(self, address: Address) -> None:
        ...

    @abstractmethod
    def get_balance(self, address: Address) -> int:
        ...

    @abstractmethod
    def set_balance(self, address: Address, balance: int) -> None:
        ...

    @abstractmethod
    def delta_balance(self, address: Address, delta: int) -> None:
        ...

    @abstractmethod
    def get_nonce(self, address: Address) -> int:
        ...

    @abstractmethod
    def set_nonce(self, address: Address, nonce: int) -> None:
        ...

    @abstractmethod
    def increment_nonce(self, address: Address) -> None:
        ...

    @abstractmethod
    def get_code(self, address: Address) -> bytes:
        ...

    @abstractmethod
    def set_code(self, address: Address, code: bytes) -> None:
        ...

    @abstractmethod
    def get_code_hash(self, address: Address) -> Hash32:
        ...

    @abstractmethod
    def delete_code(self, address: Address) -> None:
        ...

    @abstractmethod
    def has_code_or_nonce(self, address: Address) -> bool:
        ...

    @abstractmethod
    def account_exists(self, address: Address) -> bool:
        ...

    @abstractmethod
    def touch_account(self, address: Address) -> None:
        ...

    @abstractmethod
    def account_is_empty(self, address: Address) -> bool:
        ...

    #
    # Access self._chaindb
    #
    @abstractmethod
    def snapshot(self) -> Tuple[Hash32, UUID]:
        ...

    @abstractmethod
    def revert(self, snapshot: Tuple[Hash32, UUID]) -> None:
        ...

    @abstractmethod
    def commit(self, snapshot: Tuple[Hash32, UUID]) -> None:
        ...

    @abstractmethod
    def persist(self) -> None:
        ...

    #
    # Access self.prev_hashes (Read-only)
    #
    @abstractmethod
    def get_ancestor_hash(self, block_number: BlockNumber) -> Hash32:
        ...

    #
    # Computation
    #
    @abstractmethod
    def get_computation(self,
                        message: MessageAPI,
                        transaction_context: TransactionContextAPI) -> ComputationAPI:
        ...

    #
    # Transaction context
    #
    @classmethod
    @abstractmethod
    def get_transaction_context_class(cls) -> Type[TransactionContextAPI]:
        ...

    #
    # Execution
    #
    @abstractmethod
    def apply_transaction(self, transaction: SignedTransactionAPI) -> ComputationAPI:
        """
        Apply transaction to the vm state

        :param transaction: the transaction to apply
        :return: the computation
        """
        ...

    @abstractmethod
    def get_transaction_executor(self) -> TransactionExecutorAPI:
        ...

    @abstractmethod
    def costless_execute_transaction(self,
                                     transaction: SignedTransactionAPI) -> ComputationAPI:
        ...

    @abstractmethod
    def override_transaction_context(self, gas_price: int) -> ContextManager[None]:
        ...

    @abstractmethod
    def validate_transaction(self, transaction: SignedTransactionAPI) -> None:
        ...

    @classmethod
    @abstractmethod
    def get_transaction_context(cls,
                                transaction: SignedTransactionAPI) -> TransactionContextAPI:
        ...


class VirtualMachineAPI(ConfigurableAPI):
    fork: str  # noqa: E701  # flake8 bug that's fixed in 3.6.0+
    chaindb: ChainDatabaseAPI

    @abstractmethod
    def __init__(self, header: BlockHeaderAPI, chaindb: ChainDatabaseAPI) -> None:
        ...

    @property
    @abstractmethod
    def state(self) -> StateAPI:
        ...

    @classmethod
    @abstractmethod
    def build_state(cls,
                    db: AtomicDatabaseAPI,
                    header: BlockHeaderAPI,
                    chain_context: ChainContextAPI,
                    previous_hashes: Iterable[Hash32] = (),
                    ) -> StateAPI:
        ...

    @abstractmethod
    def get_header(self) -> BlockHeaderAPI:
        ...

    @abstractmethod
    def get_block(self) -> BlockAPI:
        ...

    #
    # Execution
    #
    @abstractmethod
    def apply_transaction(self,
                          header: BlockHeaderAPI,
                          transaction: SignedTransactionAPI
                          ) -> Tuple[ReceiptAPI, ComputationAPI]:
        ...

    @abstractmethod
    def execute_bytecode(self,
                         origin: Address,
                         gas_price: int,
                         gas: int,
                         to: Address,
                         sender: Address,
                         value: int,
                         data: bytes,
                         code: bytes,
                         code_address: Address = None) -> ComputationAPI:
        ...

    @abstractmethod
    def apply_all_transactions(
        self,
        transactions: Sequence[SignedTransactionAPI],
        base_header: BlockHeaderAPI
    ) -> Tuple[BlockHeaderAPI, Tuple[ReceiptAPI, ...], Tuple[ComputationAPI, ...]]:
        ...

    @abstractmethod
    def make_receipt(self,
                     base_header: BlockHeaderAPI,
                     transaction: SignedTransactionAPI,
                     computation: ComputationAPI,
                     state: StateAPI) -> ReceiptAPI:
        """
        Generate the receipt resulting from applying the transaction.

        :param base_header: the header of the block before the transaction was applied.
        :param transaction: the transaction used to generate the receipt
        :param computation: the result of running the transaction computation
        :param state: the resulting state, after executing the computation

        :return: receipt
        """
        ...

    #
    # Mining
    #
    @abstractmethod
    def import_block(self, block: BlockAPI) -> BlockAPI:
        ...

    @abstractmethod
    def mine_block(self, *args: Any, **kwargs: Any) -> BlockAPI:
        ...

    @abstractmethod
    def set_block_transactions(self,
                               base_block: BlockAPI,
                               new_header: BlockHeaderAPI,
                               transactions: Sequence[SignedTransactionAPI],
                               receipts: Sequence[ReceiptAPI]) -> BlockAPI:
        ...

    #
    # Finalization
    #
    @abstractmethod
    def finalize_block(self, block: BlockAPI) -> BlockAPI:
        ...

    @abstractmethod
    def pack_block(self, block: BlockAPI, *args: Any, **kwargs: Any) -> BlockAPI:
        ...

    #
    # Headers
    #
    @abstractmethod
    def add_receipt_to_header(self,
                              old_header: BlockHeaderAPI,
                              receipt: ReceiptAPI) -> BlockHeaderAPI:
        """
        Apply the receipt to the old header, and return the resulting header. This may have
        storage-related side-effects. For example, pre-Byzantium, the state root hash
        is included in the receipt, and so must be stored into the database.
        """
        ...

    @classmethod
    @abstractmethod
    def compute_difficulty(cls, parent_header: BlockHeaderAPI, timestamp: int) -> int:
        """
        Compute the difficulty for a block header.

        :param parent_header: the parent header
        :param timestamp: the timestamp of the child header
        """
        ...

    @abstractmethod
    def configure_header(self, **header_params: Any) -> BlockHeaderAPI:
        """
        Setup the current header with the provided parameters.  This can be
        used to set fields like the gas limit or timestamp to value different
        than their computed defaults.
        """
        ...

    @classmethod
    @abstractmethod
    def create_header_from_parent(cls,
                                  parent_header: BlockHeaderAPI,
                                  **header_params: Any) -> BlockHeaderAPI:
        """
        Creates and initializes a new block header from the provided
        `parent_header`.
        """
        ...

    #
    # Blocks
    #
    @classmethod
    @abstractmethod
    def generate_block_from_parent_header_and_coinbase(cls,
                                                       parent_header: BlockHeaderAPI,
                                                       coinbase: Address) -> BlockAPI:
        ...

    @classmethod
    @abstractmethod
    def get_block_class(cls) -> Type[BlockAPI]:
        ...

    @staticmethod
    @abstractmethod
    def get_block_reward() -> int:
        """
        Return the amount in **wei** that should be given to a miner as a reward
        for this block.

          .. note::
            This is an abstract method that must be implemented in subclasses
        """
        ...

    @classmethod
    @abstractmethod
    def get_nephew_reward(cls) -> int:
        """
        Return the reward which should be given to the miner of the given `nephew`.

          .. note::
            This is an abstract method that must be implemented in subclasses
        """
        ...

    @classmethod
    @abstractmethod
    def get_prev_hashes(cls,
                        last_block_hash: Hash32,
                        chaindb: ChainDatabaseAPI) -> Optional[Iterable[Hash32]]:
        ...

    @staticmethod
    @abstractmethod
    def get_uncle_reward(block_number: BlockNumber, uncle: BlockAPI) -> int:
        """
        Return the reward which should be given to the miner of the given `uncle`.

          .. note::
            This is an abstract method that must be implemented in subclasses
        """
        ...

    #
    # Transactions
    #
    @abstractmethod
    def create_transaction(self, *args: Any, **kwargs: Any) -> SignedTransactionAPI:
        ...

    @classmethod
    @abstractmethod
    def create_unsigned_transaction(cls,
                                    *,
                                    nonce: int,
                                    gas_price: int,
                                    gas: int,
                                    to: Address,
                                    value: int,
                                    data: bytes) -> UnsignedTransactionAPI:
        ...

    @classmethod
    @abstractmethod
    def get_transaction_class(cls) -> Type[SignedTransactionAPI]:
        ...

    #
    # Validate
    #
    @classmethod
    @abstractmethod
    def validate_receipt(self, receipt: ReceiptAPI) -> None:
        ...

    @abstractmethod
    def validate_block(self, block: BlockAPI) -> None:
        ...

    @classmethod
    @abstractmethod
    def validate_header(cls,
                        header: BlockHeaderAPI,
                        parent_header: BlockHeaderAPI,
                        check_seal: bool = True
                        ) -> None:
        ...

    @abstractmethod
    def validate_transaction_against_header(self,
                                            base_header: BlockHeaderAPI,
                                            transaction: SignedTransactionAPI) -> None:
        """
        Validate that the given transaction is valid to apply to the given header.

        :param base_header: header before applying the transaction
        :param transaction: the transaction to validate

        :raises: ValidationError if the transaction is not valid to apply
        """
        ...

    @classmethod
    @abstractmethod
    def validate_seal(cls, header: BlockHeaderAPI) -> None:
        ...

    @classmethod
    @abstractmethod
    def validate_uncle(cls,
                       block: BlockAPI,
                       uncle: BlockHeaderAPI,
                       uncle_parent: BlockHeaderAPI
                       ) -> None:
        ...

    #
    # State
    #
    @classmethod
    @abstractmethod
    def get_state_class(cls) -> Type[StateAPI]:
        ...

    @abstractmethod
    def state_in_temp_block(self) -> ContextManager[StateAPI]:
        ...


class HeaderChainAPI(ABC):
    header: BlockHeaderAPI
    chain_id: int
    vm_configuration: Tuple[Tuple[BlockNumber, Type[VirtualMachineAPI]], ...]

    @abstractmethod
    def __init__(self, base_db: AtomicDatabaseAPI, header: BlockHeaderAPI = None) -> None:
        ...

    #
    # Chain Initialization API
    #
    @classmethod
    @abstractmethod
    def from_genesis_header(cls,
                            base_db: AtomicDatabaseAPI,
                            genesis_header: BlockHeaderAPI) -> 'HeaderChainAPI':
        ...

    #
    # Helpers
    #
    @classmethod
    @abstractmethod
    def get_headerdb_class(cls) -> Type[HeaderDatabaseAPI]:
        ...

    #
    # Canonical Chain API
    #
    @abstractmethod
    def get_canonical_block_header_by_number(self, block_number: BlockNumber) -> BlockHeaderAPI:
        ...

    @abstractmethod
    def get_canonical_head(self) -> BlockHeaderAPI:
        ...

    #
    # Header API
    #
    @abstractmethod
    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeaderAPI:
        ...

    @abstractmethod
    def header_exists(self, block_hash: Hash32) -> bool:
        ...

    @abstractmethod
    def import_header(self,
                      header: BlockHeaderAPI,
                      ) -> Tuple[Tuple[BlockHeaderAPI, ...], Tuple[BlockHeaderAPI, ...]]:
        ...


class ChainAPI(ConfigurableAPI):
    vm_configuration: Tuple[Tuple[BlockNumber, Type[VirtualMachineAPI]], ...]
    chain_id: int
    chaindb: ChainDatabaseAPI

    #
    # Helpers
    #
    @classmethod
    @abstractmethod
    def get_chaindb_class(cls) -> Type[ChainDatabaseAPI]:
        ...

    #
    # Chain API
    #
    @classmethod
    @abstractmethod
    def from_genesis(cls,
                     base_db: AtomicDatabaseAPI,
                     genesis_params: Dict[str, HeaderParams],
                     genesis_state: AccountState=None) -> 'ChainAPI':
        ...

    @classmethod
    @abstractmethod
    def from_genesis_header(cls,
                            base_db: AtomicDatabaseAPI,
                            genesis_header: BlockHeaderAPI) -> 'ChainAPI':
        ...

    #
    # VM API
    #
    @classmethod
    @abstractmethod
    def get_vm_class(cls, header: BlockHeaderAPI) -> Type[VirtualMachineAPI]:
        """
        Returns the VM instance for the given block number.
        """
        ...

    @abstractmethod
    def get_vm(self, header: BlockHeaderAPI = None) -> VirtualMachineAPI:
        ...

    @classmethod
    def get_vm_class_for_block_number(cls, block_number: BlockNumber) -> Type[VirtualMachineAPI]:
        ...

    #
    # Header API
    #
    @abstractmethod
    def create_header_from_parent(self,
                                  parent_header: BlockHeaderAPI,
                                  **header_params: HeaderParams) -> BlockHeaderAPI:
        ...

    @abstractmethod
    def get_block_header_by_hash(self, block_hash: Hash32) -> BlockHeaderAPI:
        ...

    @abstractmethod
    def get_canonical_head(self) -> BlockHeaderAPI:
        ...

    @abstractmethod
    def get_score(self, block_hash: Hash32) -> int:
        ...

    #
    # Block API
    #
    @abstractmethod
    def get_ancestors(self, limit: int, header: BlockHeaderAPI) -> Tuple[BlockAPI, ...]:
        ...

    @abstractmethod
    def get_block(self) -> BlockAPI:
        ...

    @abstractmethod
    def get_block_by_hash(self, block_hash: Hash32) -> BlockAPI:
        ...

    @abstractmethod
    def get_block_by_header(self, block_header: BlockHeaderAPI) -> BlockAPI:
        ...

    @abstractmethod
    def get_canonical_block_by_number(self, block_number: BlockNumber) -> BlockAPI:
        ...

    @abstractmethod
    def get_canonical_block_hash(self, block_number: BlockNumber) -> Hash32:
        ...

    @abstractmethod
    def build_block_with_transactions(
            self,
            transactions: Tuple[SignedTransactionAPI, ...],
            parent_header: BlockHeaderAPI = None
    ) -> Tuple[BlockAPI, Tuple[ReceiptAPI, ...], Tuple[ComputationAPI, ...]]:
        ...

    #
    # Transaction API
    #
    @abstractmethod
    def create_transaction(self, *args: Any, **kwargs: Any) -> SignedTransactionAPI:
        ...

    @abstractmethod
    def create_unsigned_transaction(cls,
                                    *,
                                    nonce: int,
                                    gas_price: int,
                                    gas: int,
                                    to: Address,
                                    value: int,
                                    data: bytes) -> UnsignedTransactionAPI:
        ...

    @abstractmethod
    def get_canonical_transaction(self, transaction_hash: Hash32) -> SignedTransactionAPI:
        ...

    @abstractmethod
    def get_transaction_receipt(self, transaction_hash: Hash32) -> ReceiptAPI:
        ...

    #
    # Execution API
    #
    @abstractmethod
    def get_transaction_result(
            self,
            transaction: SignedTransactionAPI,
            at_header: BlockHeaderAPI) -> bytes:
        ...

    @abstractmethod
    def estimate_gas(
            self,
            transaction: SignedTransactionAPI,
            at_header: BlockHeaderAPI = None) -> int:
        ...

    @abstractmethod
    def import_block(self,
                     block: BlockAPI,
                     perform_validation: bool=True,
                     ) -> Tuple[BlockAPI, Tuple[BlockAPI, ...], Tuple[BlockAPI, ...]]:
        ...

    #
    # Validation API
    #
    @abstractmethod
    def validate_receipt(self, receipt: ReceiptAPI, at_header: BlockHeaderAPI) -> None:
        ...

    @abstractmethod
    def validate_block(self, block: BlockAPI) -> None:
        ...

    @abstractmethod
    def validate_seal(self, header: BlockHeaderAPI) -> None:
        ...

    @abstractmethod
    def validate_gaslimit(self, header: BlockHeaderAPI) -> None:
        ...

    @abstractmethod
    def validate_uncles(self, block: BlockAPI) -> None:
        ...

    @classmethod
    @abstractmethod
    def validate_chain(
            cls,
            root: BlockHeaderAPI,
            descendants: Tuple[BlockHeaderAPI, ...],
            seal_check_random_sample_rate: int = 1) -> None:
        ...


class MiningChainAPI(ChainAPI):
    header: BlockHeaderAPI

    @abstractmethod
    def __init__(self, base_db: AtomicDatabaseAPI, header: BlockHeaderAPI = None) -> None:
        ...

    @abstractmethod
    def apply_transaction(self,
                          transaction: SignedTransactionAPI
                          ) -> Tuple[BlockAPI, ReceiptAPI, ComputationAPI]:
        ...

    @abstractmethod
    def import_block(self,
                     block: BlockAPI,
                     perform_validation: bool=True
                     ) -> Tuple[BlockAPI, Tuple[BlockAPI, ...], Tuple[BlockAPI, ...]]:
        ...

    @abstractmethod
    def mine_block(self, *args: Any, **kwargs: Any) -> BlockAPI:
        ...

    def get_vm(self, at_header: BlockHeaderAPI = None) -> VirtualMachineAPI:
        ...
