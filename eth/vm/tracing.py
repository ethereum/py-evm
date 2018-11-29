from abc import (
    ABC,
    abstractmethod,
)

import contextlib
import logging
from typing import (
    Dict,
    List,
    NamedTuple,
    Optional,
    Tuple,
    TYPE_CHECKING,
)

from eth_utils import ValidationError

from eth.exceptions import (
    VMError,
)

from eth.vm.opcode import (
    Opcode,
)

if TYPE_CHECKING:
    # avoid circular import
    from eth.vm.computation import BaseComputation  # noqa: F401
    from trinity.chains.base import BaseAsyncChain  # noqa: F401


class TraceConfig(NamedTuple):
    debug: bool  # print output during capture end
    disable_memory: bool  # disable memory capture
    disable_stack: bool  # disable stack capture
    disable_storage: bool  # disable storage capture
    limit: int  # maximum length of output, but zero means unlimited


class StructLogEntry(NamedTuple):
    depth: int
    err: VMError
    gas: int
    gas_cost: int
    memory: Optional[bytes]
    op: str
    pc: int
    stack: Optional[Tuple[int, ...]]
    storage: Optional[Dict[int, int]]


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
    def capture(self, computation: 'BaseComputation', opcode_fn: Opcode) -> None:
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
        self.is_memory_enabled = memory
        self.is_stack_enabled = stack
        self.is_storage_enabled = storage
        self.limit = limit

        self.logs: List[StructLogEntry] = []

    @property
    def is_full(self):
        if self.limit is None:
            return False
        else:
            return len(self.logs) >= self.limit

    @property
    def is_final(self):
        return self.result is not None

    @contextlib.contextmanager
    def capture(self, computation: 'BaseComputation', opcode_fn: Opcode) -> None:
        if self.is_final:
            raise ValidationError("Cannot capture using a finalized tracer")

        pc = computation.get_pc()
        start_gas = computation.get_gas_remaining()
        stack = computation.dump_stack() if self.is_storage_enabled else None
        memory = computation.dump_memory() if self.is_memory_enabled else None

        try:
            yield
        except VMError as err:
            self._log_operation(
                depth=computation.message.depth + 1,  # TODO: why +1?
                error=err,
                gas_used=start_gas - computation.get_gas_remaining(),
                memory=memory,
                op=opcode_fn.mnemonic,
                pc=pc,
                stack=stack,
                storage={},  # TODO: implement storage dump
            )
        else:
            self._log_operation(
                depth=computation.message.depth + 1,  # TODO: why +1?
                error=None,
                gas_used=start_gas - computation.get_gas_remaining(),
                memory=memory,
                op=opcode_fn.mnemonic,
                pc=pc,
                stack=stack,
                storage={},  # TODO: implement storage dump
            )

    def finalize(self, computation: 'BaseComputation') -> None:
        if self.is_final:
            raise ValidationError("Cannot finalize tracer which is already finalized")
        elif computation.is_origin_computation:
            self.result = ExecutionResult(
                error=computation.error,
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
                       storage: Dict[bytes, bytes]) -> None:
        if self.is_full:
            self.logger.debug(
                'StructTracer full (limit=%d). Discarding trace log entry',
                self.limit,
            )
            return

        self.logs.append(StructLogEntry(
            depth=depth,
            error=error,
            gas=gas,
            gas_cost=gas_cost,
            memory=memory,
            op=op,
            pc=pc,
            stack=stack,
            storage=storage,
        ))
