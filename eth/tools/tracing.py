from abc import (
    ABC,
    abstractmethod,
)

from copy import (
    deepcopy,
)

from typing import (
    Dict,
    List,
    NamedTuple,
    Union,
    TYPE_CHECKING,
)

from eth_typing import (
    Address,
    Hash32,
)

from eth_utils import (
    decode_hex,
)

from eth.exceptions import (
    VMError,
)

from eth.vm.memory import (
    Memory,
)

from eth.vm.opcode import (
    Opcode,
)

from eth.vm.stack import (
    Stack,
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
    memory: Memory
    memory_size: int
    op: Opcode
    pc: int
    refund_counter: int
    stack: Stack
    storage: Dict[Union[int, bytes], Union[int, bytes]]


class Tracer(ABC):
    @abstractmethod
    def capture_start(self, addr_from: Address, addr_to: Address, call: bool, input: bytes,
                      gas: int, value: int) -> None:
        # initialize the tracing operation.
        raise NotImplementedError

    @abstractmethod
    def capture_state(self, computation: 'BaseComputation', pc: int, op: Opcode, gas: int,
                      gas_cost: int, memory: Memory, stack: Stack, depth: int,
                      err: VMError) -> None:
        raise NotImplementedError

    @abstractmethod
    def capture_fault(self, computation: 'BaseComputation', pc: int, op: Opcode, gas: int,
                      gas_cost: int, memory: Memory, stack: Stack, depth: int,
                      err: VMError) -> None:
        # trace an execution fault while running an opcode
        raise NotImplementedError

    @abstractmethod
    def capture_end(self, output: bytes, gas_used: int, err: VMError) -> None:
        # called after the call finishes to finalize the tracing
        raise NotImplementedError


class StructLogger(Tracer):
    def __init__(self, cfg: TraceConfig):
        self.cfg: TraceConfig = cfg
        self.logs: List[StructLogEntry] = []
        self.changed_values: Dict[Address, Dict[Union[int, bytes], Union[int, bytes]]] = {}
        self.output: bytes = None
        self.err: VMError = None

    def capture_start(self, addr_from: Address, addr_to: Address, call: bool, input: bytes,
                      gas: int, value: int) -> None:
        return None

    def capture_state(self, computation: 'BaseComputation', pc: int, op: Opcode, gas: int,
                      gas_cost: int, memory: Memory, stack: Stack, depth: int,
                      err: VMError) -> None:
        if self.cfg.limit != 0 and self.cfg.limit <= len(self.logs):
            # overflow
            return

        storage_address = computation.msg.storage_address
        if storage_address not in self.changed_values:
            self.changed_values[storage_address] = {}

        if op.mnemonic == "SSTORE" and len(stack) >= 2:
            val = stack.values[len(stack) - 2]
            slot = stack.values[len(stack) - 1]
            self.changed_values[storage_address][slot] = val

        mem_dump = None
        if not self.cfg.disable_memory:
            mem_dump = deepcopy(memory)

        stack_dump = None
        if not self.cfg.disable_stack:
            stack_dump = deepcopy(stack)

        storage_dump = None
        if not self.cfg.disable_storage:
            storage_dump = deepcopy(self.changed_values[storage_address])

        self.logs.append(StructLogEntry(depth=depth,
                                        err=err,
                                        gas=gas,
                                        gas_cost=gas_cost,
                                        memory=mem_dump,
                                        memory_size=len(mem_dump),
                                        op=op,
                                        pc=pc,
                                        stack=stack_dump,
                                        storage=storage_dump,
                                        refund_counter=computation.get_gas_refund()))

    def capture_fault(self, computation: 'BaseComputation', pc: int, op: Opcode, gas: int,
                      gas_cost: int, memory: Memory, stack: Stack, depth: int,
                      err: VMError) -> None:
        return None

    def capture_end(self, output: bytes, gas_used: int, err: VMError) -> None:
        self.output = output
        self.err = err
        """
        if self.cfg.debug:
            print(self.output)
            if self.err:
                print(self.err)
        """
        return None


class ExecutionResult(NamedTuple):
    failed: bool
    gas: int
    return_value: bytes
    struct_logs: List[StructLogEntry]


def trace_transaction(chain: 'BaseAsyncChain', tx_hash: Hash32,
                      conf: TraceConfig) -> ExecutionResult:
    (tx_block_num, tx_ix) = chain.chaindb.get_transaction_index(decode_hex(tx_hash))
    tx_block = chain.get_canonical_block_by_number(tx_block_num)
    parent_block = chain.get_canonical_block_by_number(tx_block_num - 1)
    parent_header = chain.ensure_header(parent_block.header)  # type: ignore
    vm = chain.get_vm(parent_header)
    vm.apply_all_transactions(transactions=tx_block.transactions[0:tx_ix],
                              base_header=parent_header)
    vm.state.tracer = StructLogger(conf)
    _, receipt, comp = vm.apply_transaction(vm.block.header, tx_block.transactions[tx_ix])
    return ExecutionResult(gas=receipt.gas_used,
                           failed=vm.state.tracer.err is not None,
                           return_value=comp.output,
                           struct_logs=vm.state.tracer.logs)
