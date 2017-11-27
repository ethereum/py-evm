import itertools
import logging

from evm.constants import (
    GAS_MEMORY,
    GAS_MEMORY_QUADRATIC_DENOMINATOR,
)
from evm.exceptions import (
    VMError,
)
from evm.validation import (
    validate_canonical_address,
    validate_uint256,
    validate_is_bytes,
)

from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.utils.numeric import (
    ceil32,
)

from .code_stream import (
    CodeStream,
)
from .gas_meter import (
    GasMeter,
)
from .memory import (
    Memory,
)
from .message import (
    Message,
)
from .stack import (
    Stack,
)


def memory_gas_cost(size_in_bytes):
    size_in_words = ceil32(size_in_bytes) // 32
    linear_cost = size_in_words * GAS_MEMORY
    quadratic_cost = size_in_words ** 2 // GAS_MEMORY_QUADRATIC_DENOMINATOR

    total_cost = linear_cost + quadratic_cost
    return total_cost


class Computation(object):
    """
    The execution computation
    """
    vm = None
    msg = None

    memory = None
    stack = None
    gas_meter = None

    code = None

    children = None

    _output = b''
    return_data = b''
    error = None

    logs = None
    accounts_to_delete = None

    logger = logging.getLogger('evm.vm.computation.Computation')

    def __init__(self, vm, message):
        self.vm = vm
        self.msg = message

        self.memory = Memory()
        self.stack = Stack()
        self.gas_meter = GasMeter(message.gas)

        self.children = []
        self.accounts_to_delete = {}
        self.log_entries = []

        code = message.code
        self.code = CodeStream(code)

    #
    # Convenience
    #
    @property
    def is_origin_computation(self):
        """
        Is this computation the computation initiated by a transaction.
        """
        return self.msg.is_origin

    @property
    def is_success(self):
        return self.error is None

    @property
    def is_error(self):
        return not self.is_success

    #
    # Execution
    #
    def prepare_child_message(self,
                              gas,
                              to,
                              value,
                              data,
                              code,
                              **kwargs):
        kwargs.setdefault('sender', self.msg.storage_address)

        child_message = Message(
            gas=gas,
            gas_price=self.msg.gas_price,
            origin=self.msg.origin,
            to=to,
            value=value,
            data=data,
            code=code,
            depth=self.msg.depth + 1,
            **kwargs
        )
        return child_message

    #
    # Memory Management
    #
    def extend_memory(self, start_position, size):
        validate_uint256(start_position, title="Memory start position")
        validate_uint256(size, title="Memory size")

        before_size = ceil32(len(self.memory))
        after_size = ceil32(start_position + size)

        before_cost = memory_gas_cost(before_size)
        after_cost = memory_gas_cost(after_size)

        self.logger.debug(
            "MEMORY: size (%s -> %s) | cost (%s -> %s)",
            before_size,
            after_size,
            before_cost,
            after_cost,
        )

        if size:
            if before_cost < after_cost:
                gas_fee = after_cost - before_cost
                self.gas_meter.consume_gas(
                    gas_fee,
                    reason=" ".join((
                        "Expanding memory",
                        str(before_size),
                        "->",
                        str(after_size),
                    ))
                )

            self.memory.extend(start_position, size)

    #
    # Computed properties.
    #
    @property
    def output(self):
        if self.error and self.error.zeros_return_data:
            return b''
        else:
            return self._output

    @output.setter
    def output(self, value):
        validate_is_bytes(value)
        self._output = value

    #
    # Runtime operations
    #
    def apply_child_computation(self, child_msg):
        if child_msg.is_create:
            child_computation = self.vm.apply_create_message(child_msg)
        else:
            child_computation = self.vm.apply_message(child_msg)

        self.add_child_computation(child_computation)
        return child_computation

    def add_child_computation(self, child_computation):
        if child_computation.error:
            if child_computation.msg.is_create:
                self.return_data = child_computation.output
            elif child_computation.error.zeros_return_data:
                self.return_data = b''
            else:
                self.return_data = child_computation.output
        else:
            if child_computation.msg.is_create:
                self.return_data = b''
            else:
                self.return_data = child_computation.output
        self.children.append(child_computation)

    def register_account_for_deletion(self, beneficiary):
        validate_canonical_address(beneficiary, title="Self destruct beneficiary address")

        if self.msg.storage_address in self.accounts_to_delete:
            raise ValueError(
                "Invariant.  Should be impossible for an account to be "
                "registered for deletion multiple times"
            )
        self.accounts_to_delete[self.msg.storage_address] = beneficiary

    def add_log_entry(self, account, topics, data):
        validate_canonical_address(account, title="Log entry address")
        for topic in topics:
            validate_uint256(topic, title="Log entry topic")
        validate_is_bytes(data, title="Log entry data")
        self.log_entries.append((account, topics, data))

    #
    # Getters
    #
    def get_accounts_for_deletion(self):
        if self.error:
            return tuple()
        else:
            return tuple(dict(itertools.chain(
                self.accounts_to_delete.items(),
                *(child.get_accounts_for_deletion() for child in self.children)
            )).items())

    def get_log_entries(self):
        if self.error:
            return tuple()
        else:
            return tuple(itertools.chain(
                self.log_entries,
                *(child.get_log_entries() for child in self.children)
            ))

    def get_gas_refund(self):
        if self.error:
            return 0
        else:
            return self.gas_meter.gas_refunded + sum(c.get_gas_refund() for c in self.children)

    def get_gas_used(self):
        if self.error and self.error.burns_gas:
            return self.msg.gas
        else:
            return max(
                0,
                self.msg.gas - self.gas_meter.gas_remaining,
            )

    def get_gas_remaining(self):
        if self.error and self.error.burns_gas:
            return 0
        else:
            return self.gas_meter.gas_remaining

    #
    # Context Manager API
    #
    def __enter__(self):
        self.logger.debug(
            (
                "COMPUTATION STARTING: gas: %s | from: %s | to: %s | value: %s "
                "| depth %s | static: %s"
            ),
            self.msg.gas,
            encode_hex(self.msg.sender),
            encode_hex(self.msg.to),
            self.msg.value,
            self.msg.depth,
            "y" if self.msg.is_static else "n",
        )

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_value and isinstance(exc_value, VMError):
            self.logger.debug(
                (
                    "COMPUTATION ERROR: gas: %s | from: %s | to: %s | value: %s | "
                    "depth: %s | static: %s | error: %s"
                ),
                self.msg.gas,
                encode_hex(self.msg.sender),
                encode_hex(self.msg.to),
                self.msg.value,
                self.msg.depth,
                "y" if self.msg.is_static else "n",
                exc_value,
            )
            self.error = exc_value
            if self.error.burns_gas:
                self.gas_meter.consume_gas(
                    self.gas_meter.gas_remaining,
                    reason=" ".join((
                        "Zeroing gas due to VM Exception:",
                        str(exc_value),
                    )),
                )

            # suppress VM exceptions
            return True
        elif exc_type is None:
            self.logger.debug(
                (
                    "COMPUTATION SUCCESS: from: %s | to: %s | value: %s | "
                    "depth: %s | static: %s | gas-used: %s | gas-remaining: %s"
                ),
                encode_hex(self.msg.sender),
                encode_hex(self.msg.to),
                self.msg.value,
                self.msg.depth,
                "y" if self.msg.is_static else "n",
                self.msg.gas - self.gas_meter.gas_remaining,
                self.gas_meter.gas_remaining,
            )
