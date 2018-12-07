from mypy_extensions import (
    TypedDict,
)

from typing import (
    AnyStr,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)

from eth.vm.tracing import (
    StructLogEntry,
    trace_transaction,
)

from eth_typing import (
    Hash32,
)

from eth_utils import (
    encode_hex,
    remove_0x_prefix,
)

from eth.utils.padding import (
    pad32,
)

from eth_utils.types import (
    is_string,
)

from trinity.rpc.modules import (
    RPCModule,
)


class TraceConfigRPC(TypedDict):
    debug: Optional[bool]
    disableMemory: Optional[bool]
    disableStack: Optional[bool]
    disableStorage: Optional[bool]
    limit: Optional[int]


class StructLogEntryRPC(TypedDict, total=False):
    depth: int
    error: Optional[str]
    gas: int
    gasCost: int
    memory: List[str]
    op: str
    pc: int
    stack: List[str]
    storage: Dict[int, str]


class ExecutionResultRPC(TypedDict):
    gas: int
    failed: bool
    returnValue: str
    structLogs: List[StructLogEntryRPC]


def format_struct_logs(logs: Tuple[StructLogEntry, ...]) -> List[StructLogEntryRPC]:

    def to_zeropad32_str(value: Union[AnyStr, int]) -> str:
        val: Union[AnyStr, int] = value
        if isinstance(value, int):
            hexstr = '{0:x}'.format(value)
            if len(hexstr) % 2 != 0:
                hexstr = '0' + hexstr  # avoid "Odd-length string" error
            val = bytes.fromhex(hexstr)  # type: ignore
        elif not is_string(value):
            raise TypeError("Value must be an instance of str or unicode")
        return remove_0x_prefix(encode_hex(pad32(val)))

    logs_formatted = []
    for e in logs:
        entry = StructLogEntryRPC(depth=e.depth,
                                  gas=e.gas,
                                  gasCost=e.gas_cost,
                                  memory=[],
                                  op=e.op,
                                  pc=e.pc,
                                  stack=[],
                                  storage={})
        if e.err:
            entry['error'] = str(e.err)

        i = 0
        while i + 32 <= len(e.memory):
            entry['memory'].append(remove_0x_prefix(encode_hex(e.memory[i: i + 32])))
            i += 32

        for e_ in e.stack:
            entry['stack'].append(to_zeropad32_str(e_))

        for k, v in e.storage.items():
            entry['storage'][int(k)] = to_zeropad32_str(v)

        logs_formatted.append(entry)

    return logs_formatted


class Debug(RPCModule):

    async def traceTransaction(self, tx_hash: Hash32,
                               options: TraceConfigRPC) -> ExecutionResultRPC:
        """
        Return the structured logs created during the execution of EVM
        """
        res = trace_transaction(self._chain,
                                tx_hash,
                                memory=not options.get("disableMemory", False),
                                storage=not options.get("disableStorage", False),
                                stack=not options.get("disableStack", False),
                                limit=options.get("limit", None))

        return ExecutionResultRPC(gas=res.gas,
                                  failed=res.error,
                                  returnValue=remove_0x_prefix(encode_hex(res.output)),
                                  structLogs=format_struct_logs(res.logs))
