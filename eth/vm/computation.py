import itertools
from types import (
    TracebackType,
)
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
)

from cached_property import (
    cached_property,
)
from eth_typing import (
    Address,
)
from eth_utils import (
    encode_hex,
    get_extended_debug_logger,
)

from eth._utils.datatypes import (
    Configurable,
)
from eth._utils.numeric import (
    ceil32,
)
from eth.abc import (
    CodeStreamAPI,
    ComputationAPI,
    GasMeterAPI,
    MemoryAPI,
    MessageAPI,
    OpcodeAPI,
    StackAPI,
    StateAPI,
    TransactionContextAPI,
)
from eth.constants import (
    GAS_MEMORY,
    GAS_MEMORY_QUADRATIC_DENOMINATOR,
)
from eth.exceptions import (
    Halt,
    VMError,
)
from eth.typing import (
    BytesOrView,
)
from eth.validation import (
    validate_canonical_address,
    validate_is_bytes,
    validate_uint256,
)
from eth.vm.code_stream import (
    CodeStream,
)
from eth.vm.gas_meter import (
    GasMeter,
)
from eth.vm.logic.invalid import (
    InvalidOpcode,
)
from eth.vm.memory import (
    Memory,
)
from eth.vm.message import (
    Message,
)
from eth.vm.stack import (
    Stack,
)


def NO_RESULT(computation: ComputationAPI) -> None:
    """
    This is a special method intended for usage as the "no precompile found" result.
    The type signature is designed to match the other precompiles.
    """
    raise Exception("This method is never intended to be executed")


def memory_gas_cost(size_in_bytes: int) -> int:
    size_in_words = ceil32(size_in_bytes) // 32
    linear_cost = size_in_words * GAS_MEMORY
    quadratic_cost = size_in_words**2 // GAS_MEMORY_QUADRATIC_DENOMINATOR

    total_cost = linear_cost + quadratic_cost
    return total_cost


class BaseComputation(ComputationAPI, Configurable):
    """
    The base class for all execution computations.

      .. note::

        Each :class:`~eth.vm.computation.BaseComputation` class must be configured with:

        ``opcodes``:        A mapping from the opcode integer value to the logic
                            function for the opcode.

        ``_precompiles``:   A mapping of contract address to the precompile function
                            for execution of precompiled contracts.
    """

    logger = get_extended_debug_logger("eth.vm.computation.BaseComputation")

    state: StateAPI = None
    msg: MessageAPI = None
    transaction_context: TransactionContextAPI = None
    code: CodeStreamAPI = None
    children: List[ComputationAPI] = None
    return_data: bytes = b""
    accounts_to_delete: List[Address] = None
    beneficiaries: List[Address] = None

    _memory: MemoryAPI = None
    _stack: StackAPI = None
    _gas_meter: GasMeterAPI = None
    _error: VMError = None
    _output: bytes = b""
    _log_entries: List[Tuple[int, Address, Tuple[int, ...], bytes]] = None

    # VM configuration
    opcodes: Dict[int, OpcodeAPI] = None
    _precompiles: Dict[Address, Callable[[ComputationAPI], ComputationAPI]] = None

    def __init__(
        self,
        state: StateAPI,
        message: MessageAPI,
        transaction_context: TransactionContextAPI,
    ) -> None:
        self.state = state
        self.msg = message
        self.transaction_context = transaction_context
        self.code = CodeStream(message.code)

        self._gas_meter = self._configure_gas_meter()

        self.children = []
        self.accounts_to_delete = []
        self.beneficiaries = []
        self._stack = Stack()
        self._memory = Memory()
        self._log_entries = []

    def _configure_gas_meter(self) -> GasMeter:
        return GasMeter(self.msg.gas)

    # -- class methods -- #
    @classmethod
    def apply_message(
        cls,
        state: StateAPI,
        message: MessageAPI,
        transaction_context: TransactionContextAPI,
        parent_computation: Optional[ComputationAPI] = None,
    ) -> ComputationAPI:
        raise NotImplementedError("Must be implemented by subclasses")

    @classmethod
    def apply_create_message(
        cls,
        state: StateAPI,
        message: MessageAPI,
        transaction_context: TransactionContextAPI,
        parent_computation: Optional[ComputationAPI] = None,
    ) -> ComputationAPI:
        raise NotImplementedError("Must be implemented by subclasses")

    # -- convenience -- #
    @property
    def is_origin_computation(self) -> bool:
        return self.msg.sender == self.transaction_context.origin

    # -- runtime operations -- #
    def prepare_child_message(
        self,
        gas: int,
        to: Address,
        value: int,
        data: BytesOrView,
        code: bytes,
        **kwargs: Any,
    ) -> MessageAPI:
        kwargs.setdefault("sender", self.msg.storage_address)

        child_message = Message(
            gas=gas,
            to=to,
            value=value,
            data=data,
            code=code,
            depth=self.msg.depth + 1,
            **kwargs,
        )
        return child_message

    def apply_child_computation(
        self,
        child_msg: MessageAPI,
    ) -> ComputationAPI:
        child_computation = self.generate_child_computation(child_msg)
        self.add_child_computation(child_computation)
        return child_computation

    def generate_child_computation(
        self,
        child_msg: MessageAPI,
    ) -> ComputationAPI:
        if child_msg.is_create:
            child_computation = self.apply_create_message(
                self.state,
                child_msg,
                self.transaction_context,
                parent_computation=self,
            )
        else:
            child_computation = self.apply_message(
                self.state,
                child_msg,
                self.transaction_context,
                parent_computation=self,
            )
        return child_computation

    def add_child_computation(
        self,
        child_computation: ComputationAPI,
    ) -> None:
        if child_computation.is_error:
            if child_computation.msg.is_create:
                self.return_data = child_computation.output
            elif child_computation.should_burn_gas:
                self.return_data = b""
            else:
                self.return_data = child_computation.output
        else:
            if child_computation.msg.is_create:
                self.return_data = b""
            else:
                self.return_data = child_computation.output

        self.children.append(child_computation)

    # -- gas consumption -- #
    def get_gas_refund(self) -> int:
        if self.is_error:
            return 0
        else:
            return self._gas_meter.gas_refunded + sum(
                c.get_gas_refund() for c in self.children
            )

    # -- account management -- #
    def register_account_for_deletion(self, beneficiary: Address) -> None:
        # SELFDESTRUCT

        validate_canonical_address(
            beneficiary,
            title="Self destruct beneficiary address",
        )

        if self.msg.storage_address in self.accounts_to_delete:
            raise ValueError(
                "Invariant.  Should be impossible for an account to be "
                "registered for deletion multiple times"
            )
        self.accounts_to_delete.append(self.msg.storage_address)
        self.beneficiaries.append(beneficiary)

    def get_accounts_for_deletion(self) -> List[Address]:
        # SELFDESTRUCT

        if self.is_error:
            return []
        else:
            # return accounts to delete from children and self
            return list(
                set(
                    itertools.chain(
                        *(child.get_accounts_for_deletion() for child in self.children),
                        self.accounts_to_delete,
                    )
                )
            )

    def get_self_destruct_beneficiaries(self) -> List[Address]:
        # SELFDESTRUCT

        if self.is_error:
            return []
        else:
            # return self-destruct beneficiaries from children and self
            return list(
                set(
                    itertools.chain(
                        *(
                            child.get_self_destruct_beneficiaries()
                            for child in self.children
                        ),
                        self.beneficiaries,
                    )
                )
            )

    # -- EVM logging -- #
    def add_log_entry(
        self,
        account: Address,
        topics: Tuple[int, ...],
        data: bytes,
    ) -> None:
        validate_canonical_address(account, title="Log entry address")
        for topic in topics:
            validate_uint256(topic, title="Log entry topic")
        validate_is_bytes(data, title="Log entry data")
        self._log_entries.append(
            (self.transaction_context.get_next_log_counter(), account, topics, data)
        )

    def get_raw_log_entries(
        self,
    ) -> Tuple[Tuple[int, bytes, Tuple[int, ...], bytes], ...]:
        if self.is_error:
            return ()
        else:
            return tuple(
                sorted(
                    itertools.chain(
                        self._log_entries,
                        *(child.get_raw_log_entries() for child in self.children),
                    )
                )
            )

    def get_log_entries(self) -> Tuple[Tuple[bytes, Tuple[int, ...], bytes], ...]:
        return tuple(log[1:] for log in self.get_raw_log_entries())

    # -- state transition -- #
    @classmethod
    def apply_computation(
        cls,
        state: StateAPI,
        message: MessageAPI,
        transaction_context: TransactionContextAPI,
        parent_computation: Optional[ComputationAPI] = None,
    ) -> ComputationAPI:
        with cls(state, message, transaction_context) as computation:
            if computation.is_origin_computation:
                # If origin computation, reset contracts_created
                computation.contracts_created = []

                if message.is_create:
                    # If computation is from a create transaction, consume initcode gas
                    # if >= Shanghai. CREATE and CREATE2 are handled in the opcode
                    # implementations.
                    cls.consume_initcode_gas_cost(computation)

            if parent_computation is not None:
                # If this is a child computation (has a parent computation), inherit the
                # contracts_created
                computation.contracts_created = parent_computation.contracts_created

            if message.is_create:
                # For all create messages, append the storage address to the
                # contracts_created list
                computation.contracts_created.append(message.storage_address)

            # Early exit on pre-compiles
            precompile = computation.precompiles.get(message.code_address, NO_RESULT)
            if precompile is not NO_RESULT:
                precompile(computation)
                return computation

            show_debug2 = computation.logger.show_debug2

            opcode_lookup = computation.opcodes
            for opcode in computation.code:
                try:
                    opcode_fn = opcode_lookup[opcode]
                except KeyError:
                    opcode_fn = InvalidOpcode(opcode)

                if show_debug2:
                    # We dig into some internals for debug logs
                    base_comp = cast(BaseComputation, computation)

                    try:
                        mnemonic = opcode_fn.mnemonic
                    except AttributeError:
                        mnemonic = opcode_fn.__wrapped__.mnemonic  # type: ignore

                    computation.logger.debug2(
                        f"OPCODE: 0x{opcode:x} ({mnemonic}) | "
                        f"pc: {max(0, computation.code.program_counter - 1)} | "
                        f"stack: {base_comp._stack}"
                    )

                try:
                    opcode_fn(computation=computation)
                except Halt:
                    break

        return computation

    # -- error handling -- #
    @property
    def is_success(self) -> bool:
        return self._error is None

    @property
    def is_error(self) -> bool:
        return not self.is_success

    @property
    def error(self) -> VMError:
        if self._error is not None:
            return self._error
        raise AttributeError("Computation does not have an error")

    @error.setter
    def error(self, value: VMError) -> None:
        if self._error is not None:
            raise AttributeError(f"Computation already has an error set: {self._error}")
        self._error = value

    def raise_if_error(self) -> None:
        if self._error is not None:
            raise self._error

    @property
    def should_burn_gas(self) -> bool:
        return self.is_error and self._error.burns_gas

    @property
    def should_return_gas(self) -> bool:
        return not self.should_burn_gas

    @property
    def should_erase_return_data(self) -> bool:
        return self.is_error and self._error.erases_return_data

    # -- memory management -- #
    def extend_memory(self, start_position: int, size: int) -> None:
        validate_uint256(start_position, title="Memory start position")
        validate_uint256(size, title="Memory size")

        before_size = ceil32(len(self._memory))
        after_size = ceil32(start_position + size)

        before_cost = memory_gas_cost(before_size)
        after_cost = memory_gas_cost(after_size)

        if self.logger.show_debug2:
            self.logger.debug2(
                f"MEMORY: size ({before_size} -> {after_size}) | "
                f"cost ({before_cost} -> {after_cost})"
            )

        if size:
            if before_cost < after_cost:
                gas_fee = after_cost - before_cost
                self._gas_meter.consume_gas(
                    gas_fee,
                    reason=" ".join(
                        (
                            "Expanding memory",
                            str(before_size),
                            "->",
                            str(after_size),
                        )
                    ),
                )

            self._memory.extend(start_position, size)

    def memory_write(self, start_position: int, size: int, value: bytes) -> None:
        return self._memory.write(start_position, size, value)

    def memory_read_bytes(self, start_position: int, size: int) -> bytes:
        return self._memory.read_bytes(start_position, size)

    def memory_copy(self, destination: int, source: int, length: int) -> None:
        self._memory.copy(destination, source, length)

    # -- gas consumption -- #
    def get_gas_meter(self) -> GasMeterAPI:
        return self._gas_meter

    def consume_gas(self, amount: int, reason: str) -> None:
        return self._gas_meter.consume_gas(amount, reason)

    def return_gas(self, amount: int) -> None:
        return self._gas_meter.return_gas(amount)

    def refund_gas(self, amount: int) -> None:
        return self._gas_meter.refund_gas(amount)

    def get_gas_used(self) -> int:
        if self.should_burn_gas:
            return self._gas_meter.start_gas
        else:
            return max(
                0,
                self._gas_meter.start_gas - self._gas_meter.gas_remaining,
            )

    def get_gas_remaining(self) -> int:
        if self.should_burn_gas:
            return 0
        else:
            return self._gas_meter.gas_remaining

    @classmethod
    def consume_initcode_gas_cost(cls, computation: ComputationAPI) -> None:
        # this method does not become relevant until the Shanghai hard fork
        """
        Before starting the computation, consume initcode gas cost.
        """

    # -- stack management -- #
    def stack_swap(self, position: int) -> None:
        return self._stack.swap(position)

    def stack_dup(self, position: int) -> None:
        return self._stack.dup(position)

    # Stack manipulation is performance-sensitive code.
    # Avoid method call overhead by proxying stack method directly to stack object

    @cached_property
    def stack_pop_ints(self) -> Callable[[int], Tuple[int, ...]]:
        return self._stack.pop_ints

    @cached_property
    def stack_pop_bytes(self) -> Callable[[int], Tuple[bytes, ...]]:
        return self._stack.pop_bytes

    @cached_property
    def stack_pop_any(self) -> Callable[[int], Tuple[Union[int, bytes], ...]]:
        return self._stack.pop_any

    @cached_property
    def stack_pop1_int(self) -> Callable[[], int]:
        return self._stack.pop1_int

    @cached_property
    def stack_pop1_bytes(self) -> Callable[[], bytes]:
        return self._stack.pop1_bytes

    @cached_property
    def stack_pop1_any(self) -> Callable[[], Union[int, bytes]]:
        return self._stack.pop1_any

    @cached_property
    def stack_push_int(self) -> Callable[[int], None]:
        return self._stack.push_int

    @cached_property
    def stack_push_bytes(self) -> Callable[[bytes], None]:
        return self._stack.push_bytes

    # -- computation result -- #
    @property
    def output(self) -> bytes:
        if self.should_erase_return_data:
            return b""
        else:
            return self._output

    @output.setter
    def output(self, value: bytes) -> None:
        validate_is_bytes(value)
        self._output = value

    # -- opcode API -- #
    @property
    def precompiles(self) -> Dict[Address, Callable[[ComputationAPI], Any]]:
        if self._precompiles is None:
            return {}
        else:
            return self._precompiles

    @classmethod
    def get_precompiles(cls) -> Dict[Address, Callable[[ComputationAPI], Any]]:
        if cls._precompiles is None:
            return {}
        else:
            return cls._precompiles

    def get_opcode_fn(self, opcode: int) -> OpcodeAPI:
        try:
            return self.opcodes[opcode]
        except KeyError:
            return InvalidOpcode(opcode)

    # -- context manager API -- #
    def __enter__(self) -> ComputationAPI:
        if self.logger.show_debug2:
            self.logger.debug2(
                (
                    "MESSAGE COMPUTATION STARTING: "
                    f"from: {encode_hex(self.msg.sender)} | "
                    f"to: {encode_hex(self.msg.to)} | "
                    f"value: {self.msg.value} | "
                    f"depth: {self.msg.depth} | "
                    f"static: {'y' if self.msg.is_static else 'n'} | "
                    f"gas: {self.msg.gas}"
                ),
            )
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        if exc_value and isinstance(exc_value, VMError):
            if self.logger.show_debug2:
                self.logger.debug2(
                    (
                        "COMPUTATION ERROR: "
                        f"gas: {self.msg.gas} | "
                        f"from: {encode_hex(self.msg.sender)} | "
                        f"to: {encode_hex(self.msg.to)} | "
                        f"value: {self.msg.value} | "
                        f"depth: {self.msg.depth} | "
                        f"static: {'y' if self.msg.is_static else 'n'} | "
                        f"error: {exc_value}"
                    ),
                )

            self._error = exc_value
            if self.should_burn_gas:
                self.consume_gas(
                    self._gas_meter.gas_remaining,
                    reason=" ".join(
                        (
                            "Zeroing gas due to VM Exception:",
                            str(exc_value),
                        )
                    ),
                )

            # when we raise an exception that erases return data, erase the return data
            if self.should_erase_return_data:
                self.return_data = b""

            # suppress VM exceptions
            return True

        elif exc_type is None and self.logger.show_debug2:
            self.logger.debug2(
                (
                    "COMPUTATION SUCCESS: "
                    f"from: {encode_hex(self.msg.sender)} | "
                    f"to: {encode_hex(self.msg.to)} | "
                    f"value: {self.msg.value} | "
                    f"depth: {self.msg.depth} | "
                    f"static: {'y' if self.msg.is_static else 'n'} | "
                    f"gas-used: {self.get_gas_used()} | "
                    f"gas-remaining: {self._gas_meter.gas_remaining}"
                ),
            )

        return None
