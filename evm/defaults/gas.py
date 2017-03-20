from evm import gas



def not_implemented(name):
    def fn(*args, **kwargs):
        raise NotImplementedError("The {0} opcode has not been implemented".format(name))
    return fn


OPCODE_LOOKUP = {
    #
    # Arithmetic
    #
    opcode_values.STOP: gas.GAS_ZERO,
    opcode_values.ADD: gas.GAS_VERYLOW,
    opcode_values.MUL: gas.GAS_LOW,
    opcode_values.SUB: gas.GAS_VERYLOW,
    opcode_values.DIV: gas.GAS_LOW,
    opcode_values.SDIV: gas.GAS_LOW,
    opcode_values.MOD: gas.GAS_LOW,
    opcode_values.SMOD: gas.GAS_LOW,
    opcode_values.ADDMOD: gas.GAS_MID,
    opcode_values.MULMOD: gas.GAS_MID,
    opcode_values.EXP: gas.GAS_EXP,
    opcode_values.SIGNEXTEND: gas.GAS_LOW,
    #
    # Comparisons
    #
    opcode_values.LT: gas.GAS_VERYLOW,
    opcode_values.GT: gas.GAS_VERYLOW,
    opcode_values.SLT: gas.GAS_VERYLOW,
    opcode_values.SGT: gas.GAS_VERYLOW,
    opcode_values.EQ: gas.GAS_VERYLOW,
    opcode_values.ISZERO: gas.GAS_VERYLOW,
    opcode_values.AND: gas.GAS_VERYLOW,
    opcode_values.OR: gas.GAS_VERYLOW,
    opcode_values.XOR: gas.GAS_VERYLOW,
    opcode_values.NOT: gas.GAS_VERYLOW,
    opcode_values.BYTE: gas.GAS_VERYLOW,
    #
    # Sha3
    #
    opcode_values.SHA3: gas.GAS_SHA3,
    #
    # Environment Information
    #
    opcode_values.ADDRESS: gas.GAS_BASE,
    opcode_values.BALANCE: gas.GAS_BALANCE,
    opcode_values.ORIGIN: gas.GAS_BASE,
    opcode_values.CALLER: gas.GAS_BASE,
    opcode_values.CALLVALUE: gas.GAS_BASE,
    opcode_values.CALLDATALOAD: gas.GAS_VERYLOW,
    opcode_values.CALLDATASIZE: gas.GAS_BASE,
    opcode_values.CALLDATACOPY: gas.GAS_VERYLOW,
    opcode_values.CODESIZE: gas.GAS_BASE,
    opcode_values.CODECOPY: gas.GAS_VERYLOW,
    opcode_values.GASPRICE: gas.GAS_BASE,
    opcode_values.EXTCODESIZE: gas.GAS_EXTCODE,
    opcode_values.EXTCODECOPY: gas.GAS_EXTCODE,
    #
    # Block Information
    #
    opcode_values.BLOCKHASH: gas.GAS_BLOCKHASH,
    opcode_values.COINBASE: gas.GAS_BASE,
    opcode_values.TIMESTAMP: gas.GAS_BASE,
    opcode_values.NUMBER: gas.GAS_BASE,
    opcode_values.DIFFICULTY: gas.GAS_BASE,
    opcode_values.GASLIMIT: gas.GAS_BASE,
    #
    # Stack, Memory, Storage and Flow Operations
    #
    opcode_values.POP: gas.GAS_BASE,
    opcode_values.MLOAD: gas.GAS_VERYLOW,
    opcode_values.MSTORE: gas.GAS_VERYLOW,
    opcode_values.MSTORE8: gas.GAS_VERYLOW,
    opcode_values.SLOAD: gas.GAS_SLOAD,
    opcode_values.SSTORE: gas.GAS_NULL,
    opcode_values.JUMP: gas.GAS_MID,
    opcode_values.JUMPI: gas.GAS_HIGH,
    opcode_values.PC: gas.GAS_BASE,
    opcode_values.MSIZE: gas.GAS_BASE,
    opcode_values.GAS: gas.GAS_BASE,
    opcode_values.JUMPDEST: gas.GAS_JUMPDEST,
    #
    # Push Operations
    #
    opcode_values.PUSH1: gas.GAS_VERYLOW,
    opcode_values.PUSH2: gas.GAS_VERYLOW,
    opcode_values.PUSH3: gas.GAS_VERYLOW,
    opcode_values.PUSH4: gas.GAS_VERYLOW,
    opcode_values.PUSH5: gas.GAS_VERYLOW,
    opcode_values.PUSH6: gas.GAS_VERYLOW,
    opcode_values.PUSH7: gas.GAS_VERYLOW,
    opcode_values.PUSH8: gas.GAS_VERYLOW,
    opcode_values.PUSH9: gas.GAS_VERYLOW,
    opcode_values.PUSH10: gas.GAS_VERYLOW,
    opcode_values.PUSH11: gas.GAS_VERYLOW,
    opcode_values.PUSH12: gas.GAS_VERYLOW,
    opcode_values.PUSH13: gas.GAS_VERYLOW,
    opcode_values.PUSH14: gas.GAS_VERYLOW,
    opcode_values.PUSH15: gas.GAS_VERYLOW,
    opcode_values.PUSH16: gas.GAS_VERYLOW,
    opcode_values.PUSH17: gas.GAS_VERYLOW,
    opcode_values.PUSH18: gas.GAS_VERYLOW,
    opcode_values.PUSH19: gas.GAS_VERYLOW,
    opcode_values.PUSH20: gas.GAS_VERYLOW,
    opcode_values.PUSH21: gas.GAS_VERYLOW,
    opcode_values.PUSH22: gas.GAS_VERYLOW,
    opcode_values.PUSH23: gas.GAS_VERYLOW,
    opcode_values.PUSH24: gas.GAS_VERYLOW,
    opcode_values.PUSH25: gas.GAS_VERYLOW,
    opcode_values.PUSH26: gas.GAS_VERYLOW,
    opcode_values.PUSH27: gas.GAS_VERYLOW,
    opcode_values.PUSH28: gas.GAS_VERYLOW,
    opcode_values.PUSH29: gas.GAS_VERYLOW,
    opcode_values.PUSH30: gas.GAS_VERYLOW,
    opcode_values.PUSH31: gas.GAS_VERYLOW,
    opcode_values.PUSH32: gas.GAS_VERYLOW,
    #
    # Duplicate Operations
    #
    opcode_values.DUP1: gas.GAS_VERYLOW,
    opcode_values.DUP2: gas.GAS_VERYLOW,
    opcode_values.DUP3: gas.GAS_VERYLOW,
    opcode_values.DUP4: gas.GAS_VERYLOW,
    opcode_values.DUP5: gas.GAS_VERYLOW,
    opcode_values.DUP6: gas.GAS_VERYLOW,
    opcode_values.DUP7: gas.GAS_VERYLOW,
    opcode_values.DUP8: gas.GAS_VERYLOW,
    opcode_values.DUP9: gas.GAS_VERYLOW,
    opcode_values.DUP10: gas.GAS_VERYLOW,
    opcode_values.DUP11: gas.GAS_VERYLOW,
    opcode_values.DUP12: gas.GAS_VERYLOW,
    opcode_values.DUP13: gas.GAS_VERYLOW,
    opcode_values.DUP14: gas.GAS_VERYLOW,
    opcode_values.DUP15: gas.GAS_VERYLOW,
    opcode_values.DUP16: gas.GAS_VERYLOW,
    #
    # Exchange Operations
    #
    opcode_values.SWAP1: gas.GAS_VERYLOW,
    opcode_values.SWAP2: gas.GAS_VERYLOW,
    opcode_values.SWAP3: gas.GAS_VERYLOW,
    opcode_values.SWAP4: gas.GAS_VERYLOW,
    opcode_values.SWAP5: gas.GAS_VERYLOW,
    opcode_values.SWAP6: gas.GAS_VERYLOW,
    opcode_values.SWAP7: gas.GAS_VERYLOW,
    opcode_values.SWAP8: gas.GAS_VERYLOW,
    opcode_values.SWAP9: gas.GAS_VERYLOW,
    opcode_values.SWAP10: gas.GAS_VERYLOW,
    opcode_values.SWAP11: gas.GAS_VERYLOW,
    opcode_values.SWAP12: gas.GAS_VERYLOW,
    opcode_values.SWAP13: gas.GAS_VERYLOW,
    opcode_values.SWAP14: gas.GAS_VERYLOW,
    opcode_values.SWAP15: gas.GAS_VERYLOW,
    opcode_values.SWAP16: gas.GAS_VERYLOW,
    #
    # Logging
    #
    opcode_values.LOG0: gas.GAS_LOG,
    opcode_values.LOG1: gas.GAS_LOG,
    opcode_values.LOG2: gas.GAS_LOG,
    opcode_values.LOG3: gas.GAS_LOG,
    opcode_values.LOG4: gas.GAS_LOG,
    #
    # System
    #
    opcode_values.CREATE: gas.GAS_CREATE,
    opcode_values.CALL: gas.GAS_NULL,
    opcode_values.CALLCODE: gas.GAS_NULL,
    opcode_values.RETURN: gas.GAS_ZERO,
    opcode_values.DELEGATECALL: gas.GAS_NULL,
    opcode_values.SUICIDE: gas.GAS_NULL,
}
