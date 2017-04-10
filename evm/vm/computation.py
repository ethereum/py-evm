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
    evm = None
    msg = None

    memory = None
    stack = None
    gas_meter = None

    code = None

    children = None

    output = b''
    error = None

    logs = None
    accounts_to_delete = None

    logger = logging.getLogger('evm.vm.computation.Computation')

    def __init__(self, evm, message):
        self.evm = evm
        self.msg = message

        self.memory = Memory()
        self.stack = Stack()
        self.gas_meter = GasMeter(message.gas)

        self.children = []
        self.accounts_to_delete = {}
        self.log_entries = []

        if message.is_create:
            code = message.data
        else:
            code = self.evm.block.state_db.get_code(message.code_address)
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

    #
    # Execution
    #
    def prepare_child_message(self,
                              gas,
                              to,
                              value,
                              data,
                              sender=None,
                              code_address=None,
                              create_address=None):
        if sender is None:
            sender = self.msg.to

        child_message = Message(
            gas=gas,
            gas_price=self.msg.gas_price,
            origin=self.msg.origin,
            to=to,
            sender=sender,
            value=value,
            data=data,
            depth=self.msg.depth + 1,
            code_address=code_address,
            create_address=create_address,
        )
        return child_message

    def apply_child_message(self, message):
        if message.is_create:
            child_computation = self.evm.apply_create_message(message)
        else:
            child_computation = self.evm.apply_message(message)

        self.children.append(child_computation)
        return child_computation

    #
    # Memory Management
    #
    def extend_memory(self, start_position, size):
        validate_uint256(start_position)
        validate_uint256(size)

        before_size = ceil32(len(self.memory))
        after_size = ceil32(start_position + size)

        before_cost = memory_gas_cost(before_size)
        after_cost = memory_gas_cost(after_size)

        if self.logger is not None:
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
    # Runtime Operations
    #
    def register_account_for_deletion(self, beneficiary):
        validate_canonical_address(beneficiary)

        if self.msg.to in self.accounts_to_delete:
            raise ValueError(
                "Invariant.  Should be impossible for an account to be "
                "registered for deletion multiple times"
            )
        self.accounts_to_delete[self.msg.to] = beneficiary

    def get_accounts_for_deletion(self):
        if self.error:
            return tuple(dict().items())
        else:
            return tuple(dict(itertools.chain(
                self.accounts_to_delete.items(),
                *(child.get_accounts_for_deletion() for child in self.children)
            )).items())

    def add_log_entry(self, account, topics, data):
        self.log_entries.append((account, topics, data))

    def get_log_entries(self):
        if self.error:
            return tuple()
        else:
            return tuple(itertools.chain(
                self.log_entries,
                *(child.get_log_entries() for child in self.children)
            ))

    #
    # Context Manager API
    #
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type and issubclass(exc_type, VMError):
            self.error = exc_value
            # suppress VM exceptions
            return True
