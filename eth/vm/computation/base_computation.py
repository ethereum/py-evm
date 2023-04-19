from types import TracebackType
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from cached_property import cached_property

from eth_typing import (
    Address,
)
from eth_utils import (
    get_extended_debug_logger,
)

from eth._utils.datatypes import (
    Configurable,
)
from eth._utils.numeric import (
    ceil32,
)
from eth.abc import (
    ComputationAPI,
    MemoryAPI,
    StackAPI,
    GasMeterAPI,
    OpcodeAPI,
    CodeStreamAPI,
    MessageComputationAPI,
    StateAPI,
)
from eth.constants import (
    GAS_MEMORY,
    GAS_MEMORY_QUADRATIC_DENOMINATOR,
)
from eth.exceptions import (
    VMError,
)
from eth.validation import (
    validate_is_bytes,
    validate_uint256,
)
from eth.vm.logic.invalid import (
    InvalidOpcode,
)
from eth.vm.memory import (
    Memory,
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
    quadratic_cost = size_in_words ** 2 // GAS_MEMORY_QUADRATIC_DENOMINATOR

    total_cost = linear_cost + quadratic_cost
    return total_cost


C = TypeVar("C", bound="ComputationAPI")


class BaseComputation(ComputationAPI, Configurable, Generic[C]):
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
    code: CodeStreamAPI = None
    children: List[C] = None
    return_data: bytes = b''

    _memory: MemoryAPI = None
    _stack: StackAPI = None
    _gas_meter: GasMeterAPI = None
    _error: VMError = None
    _output: bytes = b''

    # VM configuration
    opcodes: Dict[int, OpcodeAPI] = None
    _precompiles: Dict[Address, Callable[[ComputationAPI], ComputationAPI]] = None

    def __init__(self, state: StateAPI) -> None:
        self.state = state
        self.children = []

        self._memory = Memory()
        self._stack = Stack()

    def _configure_gas_meter(self) -> GasMeterAPI:
        raise NotImplementedError("Must be implemented by subclasses")

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
                "MEMORY: size (%s -> %s) | cost (%s -> %s)",
                before_size,
                after_size,
                before_cost,
                after_cost,
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
                    )
                )

            self._memory.extend(start_position, size)

    def memory_write(self, start_position: int, size: int, value: bytes) -> None:
        return self._memory.write(start_position, size, value)

    def memory_read(self, start_position: int, size: int) -> memoryview:
        return self._memory.read(start_position, size)

    def memory_read_bytes(self, start_position: int, size: int) -> bytes:
        return self._memory.read_bytes(start_position, size)

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
    def consume_initcode_gas_cost(cls, computation: MessageComputationAPI) -> None:
        # this method does not become relevant until the Shanghai hard fork
        """
        Before starting the computation, consume initcode gas cost.
        """
        pass

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
            return b''
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
            self.logger.debug2("COMPUTATION STARTING")
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Union[None, bool]:
        if exc_value and isinstance(exc_value, VMError):
            # Exception handling logic for computations is done here in the base class.
            # Subclass-specific logging can be done in each subclass by overriding
            # `__exit__` and calling `super().__exit__(exc_type, exc_value, traceback)`.
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
                self.return_data = b''

            # suppress VM exceptions
            return True

        return None
