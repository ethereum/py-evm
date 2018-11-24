from mypy_extensions import (
    TypedDict,
)

from typing import (
    AnyStr,
    Dict,
    List,
    Optional,
    Union,
)

from eth.tools.tracing import (
    StructLogEntry,
    TraceConfig,
    trace_transaction,
)

from eth_utils import (
    decode_hex,
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


def format_struct_logs(logs: List[StructLogEntry]) -> List[StructLogEntryRPC]:

    def to_zeropad32_str(value: Union[AnyStr, int]) -> str:
        if isinstance(value, int):
            zp_str = "{0:#0{1}x}".format(value, 4)  # avoid "Odd-length string" error in decode_hex
            value = decode_hex(zp_str)
        elif not is_string(value):
            raise TypeError("Value must be an instance of str or unicode")
        return remove_0x_prefix(encode_hex(pad32(value)))

    logs_formatted = []
    for e in logs:
        entry = StructLogEntryRPC(depth=e.depth,
                                  gas=e.gas,
                                  gasCost=e.gas_cost,
                                  memory=[],
                                  op=e.op.mnemonic,
                                  pc=e.pc,
                                  stack=[],
                                  storage={})
        if e.err:
            entry['error'] = str(e.err)

        i = 0
        while i + 32 <= len(e.memory):
            entry['memory'].append(remove_0x_prefix(encode_hex(e.memory.read(i, 32))))
            i += 32

        for e_ in e.stack.values:
            entry['stack'].append(to_zeropad32_str(e_))

        for k, v in e.storage.items():
            entry['storage'][int(k)] = to_zeropad32_str(v)

        logs_formatted.append(entry)

    return logs_formatted


class Debug(RPCModule):

    async def traceTransaction(self, tx_hash: str, options: TraceConfigRPC) -> ExecutionResultRPC:
        """
        Return the structured logs created during the execution of EVM
        """
        res = trace_transaction(self._chain, tx_hash,
                                TraceConfig(debug=options.get("debug", False),
                                            disable_memory=options.get("disableMemory", False),
                                            disable_storage=options.get("disableStorage", False),
                                            disable_stack=options.get("disableStack", False),
                                            limit=options.get("limit", 0)))

        return ExecutionResultRPC(gas=res.gas,
                                  failed=res.failed,
                                  returnValue=remove_0x_prefix(encode_hex(res.return_value)),
                                  structLogs=format_struct_logs(res.struct_logs))
