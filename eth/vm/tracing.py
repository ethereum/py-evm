from abc import (
    ABC,
    abstractmethod,
)

import contextlib

import logging

from typing import (
    Dict,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Tuple,
    TYPE_CHECKING,
    Union,
)

from eth_typing import (
    Address,
    Hash32,
)

from eth_utils import (
    decode_hex,
    ValidationError,
)

from eth.exceptions import (
    VMError,
)

from eth.vm.opcode import (
    Opcode,
)

if TYPE_CHECKING:
    # avoid circular import
    from eth.vm.computation import BaseComputation  # noqa: F401
    from trinity.chains.base import BaseAsyncChain   # noqa: F401


class Storage(object):
    __slots__ = ['store']

    def __init__(self) -> None:
        self.store = {}  # type: Dict[Address, Dict[int, Union[int, bytes]]]

    def dump(self, address: Address) -> Dict[int, Union[int, bytes]]:
        if address not in self.store:
            return {}
        return self.store[address]

    def set_slot(self, address: Address, slot: int, value: Union[int, bytes]) -> None:
        if address not in self.store:
            self.store[address] = {}
        self.store[address][slot] = value

    def set_address(self, address: Address, slots: Dict[int, Union[int, bytes]]) -> None:
        self.store[address] = slots


class StructLogEntry(NamedTuple):
    depth: int
    err: VMError
    gas: int
    gas_cost: int
    memory: Optional[bytes]
    op: str
    pc: int
    stack: Optional[Tuple[int, ...]]
    storage: Optional[Dict[int, Union[int, bytes]]]


class BaseTracer(ABC):
    @contextlib.contextmanager
    @abstractmethod
    def capture(self, computation: 'BaseComputation', opcode_fn: Opcode) -> None:
        pass

    @abstractmethod
    def finalize(self, computation: 'BaseComputation') -> None:
        pass


class NoopTracer(BaseTracer):
    """
    A Tracer class which does nothing.
    """
    @contextlib.contextmanager
    def capture(self, computation: 'BaseComputation', opcode_fn: Opcode) -> Iterator[None]:
        yield

    def finalize(self, computation: 'BaseComputation') -> None:
        pass


class ExecutionResult(NamedTuple):
    error: bool
    gas: int
    output: bytes
    logs: Tuple[StructLogEntry, ...]


class StructTracer(BaseTracer):
    """
    A Tracer class which implements structured log tracing:

    https://github.com/ethereum/go-ethereum/wiki/Tracing:-Introduction
    """
    logger = logging.getLogger('eth.vm.tracing.StructTracer')

    result = None

    def __init__(self,
                 memory: bool = True,
                 stack: bool = True,
                 storage: bool = True,
                 limit: int = None):
        self.changed_values = Storage()
        self.is_memory_enabled = memory
        self.is_stack_enabled = stack
        self.is_storage_enabled = storage
        self.limit = limit
        self.logs: List[StructLogEntry] = []

    @property
    def is_full(self) -> bool:
        if self.limit is None:
            return False
        else:
            return len(self.logs) >= self.limit

    @property
    def is_final(self) -> bool:
        return self.result is not None

    @contextlib.contextmanager
    def capture(self, computation: 'BaseComputation', opcode_fn: Opcode) -> Iterator[None]:
        if self.is_final:
            raise ValidationError("Cannot capture using a finalized tracer")

        pc = computation.get_pc()
        start_gas = computation.get_gas_remaining()
        stack = computation.dump_stack() if self.is_storage_enabled else None
        memory = computation.dump_memory() if self.is_memory_enabled else None

        if self.is_storage_enabled:
            storage_address = computation.msg.storage_address
            if opcode_fn.mnemonic == "SSTORE" and len(stack) >= 2:
                val = stack[len(stack) - 2]
                slot = stack[len(stack) - 1]
                self.changed_values.set_slot(storage_address, slot, val)
            storage = self.changed_values.dump(storage_address)
        else:
            storage = None

        try:
            yield
        except VMError as err:
            self._log_operation(
                depth=computation.msg.depth + 1,
                error=err,
                gas=start_gas,
                gas_cost=start_gas - computation.get_gas_remaining(),
                memory=memory,
                op=opcode_fn.mnemonic,
                pc=pc,
                stack=stack,
                storage=storage
            )
            raise
        else:
            self._log_operation(
                depth=computation.msg.depth + 1,
                error=None,
                gas=start_gas,
                gas_cost=start_gas - computation.get_gas_remaining(),
                memory=memory,
                op=opcode_fn.mnemonic,
                pc=pc,
                stack=stack,
                storage=storage
            )

    def finalize(self, computation: 'BaseComputation') -> None:
        if self.is_final:
            raise ValidationError("Cannot finalize tracer which is already finalized")
        elif computation.is_origin_computation:
            self.result = ExecutionResult(
                error=computation.error is not None,
                gas=computation.get_gas_used(),
                logs=tuple(self.logs),
                output=computation.output,
            )

    def _log_operation(self,
                       *,
                       depth: int,
                       error: Optional[VMError],
                       gas: int,
                       gas_cost: int,
                       memory: bytes,
                       op: str,
                       pc: int,
                       stack: Tuple[int, ...],
                       storage: Dict[int, Union[int, bytes]]) -> None:
        if self.is_full:
            self.logger.debug(
                'StructTracer full (limit=%d). Discarding trace log entry',
                self.limit,
            )
            return

        self.logs.append(StructLogEntry(
            depth=depth,
            err=error,
            gas=gas,
            gas_cost=gas_cost,
            memory=memory,
            op=op,
            pc=pc,
            stack=stack,
            storage=storage,
        ))


def trace_transaction(chain: 'BaseAsyncChain', tx_hash: Hash32, memory: bool, stack: bool,
                      storage: bool, limit: int) -> ExecutionResult:
    (tx_block_num, tx_ix) = chain.chaindb.get_transaction_index(decode_hex(tx_hash))
    tx_block = chain.get_canonical_block_by_number(tx_block_num)
    parent_block = chain.get_canonical_block_by_number(tx_block_num - 1)
    parent_header = chain.ensure_header(parent_block.header)  # type: ignore
    vm = chain.get_vm(parent_header)
    vm.apply_all_transactions(transactions=tx_block.transactions[0:tx_ix],
                              base_header=parent_header)
    tracer = StructTracer(memory, stack, storage, limit)
    _, receipt, comp = vm.apply_transaction(vm.block.header,
                                            tx_block.transactions[tx_ix],
                                            tracer=tracer)
    return tracer.result
