from . import values
from . import mnemonics


MNEMONIC_LOOKUP = {
    #
    # Arithmetic
    #
    values.STOP: mnemonics.STOP,
    values.ADD: mnemonics.ADD,
    values.MUL: mnemonics.MUL,
    values.SUB: mnemonics.SUB,
    values.DIV: mnemonics.DIV,
    values.SDIV: mnemonics.SDIV,
    values.MOD: mnemonics.MOD,
    values.SMOD: mnemonics.SMOD,
    values.ADDMOD: mnemonics.ADDMOD,
    values.MULMOD: mnemonics.MULMOD,
    values.EXP: mnemonics.EXP,
    values.SIGNEXTEND: mnemonics.SIGNEXTEND,
    #
    # Comparisons
    #
    values.LT: mnemonics.LT,
    values.GT: mnemonics.GT,
    values.SLT: mnemonics.SLT,
    values.SGT: mnemonics.SGT,
    values.EQ: mnemonics.EQ,
    values.ISZERO: mnemonics.ISZERO,
    values.AND: mnemonics.AND,
    values.OR: mnemonics.OR,
    values.XOR: mnemonics.XOR,
    values.NOT: mnemonics.NOT,
    values.BYTE: mnemonics.BYTE,
    #
    # Sha3
    #
    values.SHA3: mnemonics.SHA3,
    #
    # Environment Information
    #
    values.ADDRESS: mnemonics.ADDRESS,
    values.BALANCE: mnemonics.BALANCE,
    values.ORIGIN: mnemonics.ORIGIN,
    values.CALLER: mnemonics.CALLER,
    values.CALLVALUE: mnemonics.CALLVALUE,
    values.CALLDATALOAD: mnemonics.CALLDATALOAD,
    values.CALLDATASIZE: mnemonics.CALLDATASIZE,
    values.CALLDATACOPY: mnemonics.CALLDATACOPY,
    values.CODESIZE: mnemonics.CODESIZE,
    values.CODECOPY: mnemonics.CODECOPY,
    values.GASPRICE: mnemonics.GASPRICE,
    values.EXTCODESIZE: mnemonics.EXTCODESIZE,
    values.EXTCODECOPY: mnemonics.EXTCODECOPY,
    #
    # Block Information
    #
    values.BLOCKHASH: mnemonics.BLOCKHASH,
    values.COINBASE: mnemonics.COINBASE,
    values.TIMESTAMP: mnemonics.TIMESTAMP,
    values.NUMBER: mnemonics.NUMBER,
    values.DIFFICULTY: mnemonics.DIFFICULTY,
    values.GASLIMIT: mnemonics.GASLIMIT,
    #
    # Stack, Memory, Storage and Flow Operations
    #
    values.POP: mnemonics.POP,
    values.MLOAD: mnemonics.MLOAD,
    values.MSTORE: mnemonics.MSTORE,
    values.MSTORE8: mnemonics.MSTORE8,
    values.SLOAD: mnemonics.SLOAD,
    values.SSTORE: mnemonics.SSTORE,
    values.JUMP: mnemonics.JUMP,
    values.JUMPI: mnemonics.JUMPI,
    values.PC: mnemonics.PC,
    values.MSIZE: mnemonics.MSIZE,
    values.GAS: mnemonics.GAS,
    values.JUMPDEST: mnemonics.JUMPDEST,
    #
    # Push Operations
    #
    values.PUSH1: mnemonics.PUSH1,
    values.PUSH2: mnemonics.PUSH2,
    values.PUSH3: mnemonics.PUSH3,
    values.PUSH4: mnemonics.PUSH4,
    values.PUSH5: mnemonics.PUSH5,
    values.PUSH6: mnemonics.PUSH6,
    values.PUSH7: mnemonics.PUSH7,
    values.PUSH8: mnemonics.PUSH8,
    values.PUSH9: mnemonics.PUSH9,
    values.PUSH10: mnemonics.PUSH10,
    values.PUSH11: mnemonics.PUSH11,
    values.PUSH12: mnemonics.PUSH12,
    values.PUSH13: mnemonics.PUSH13,
    values.PUSH14: mnemonics.PUSH14,
    values.PUSH15: mnemonics.PUSH15,
    values.PUSH16: mnemonics.PUSH16,
    values.PUSH17: mnemonics.PUSH17,
    values.PUSH18: mnemonics.PUSH18,
    values.PUSH19: mnemonics.PUSH19,
    values.PUSH20: mnemonics.PUSH20,
    values.PUSH21: mnemonics.PUSH21,
    values.PUSH22: mnemonics.PUSH22,
    values.PUSH23: mnemonics.PUSH23,
    values.PUSH24: mnemonics.PUSH24,
    values.PUSH25: mnemonics.PUSH25,
    values.PUSH26: mnemonics.PUSH26,
    values.PUSH27: mnemonics.PUSH27,
    values.PUSH28: mnemonics.PUSH28,
    values.PUSH29: mnemonics.PUSH29,
    values.PUSH30: mnemonics.PUSH30,
    values.PUSH31: mnemonics.PUSH31,
    values.PUSH32: mnemonics.PUSH32,
    #
    # Duplicate Operations
    #
    values.DUP1: mnemonics.DUP1,
    values.DUP2: mnemonics.DUP2,
    values.DUP3: mnemonics.DUP3,
    values.DUP4: mnemonics.DUP4,
    values.DUP5: mnemonics.DUP5,
    values.DUP6: mnemonics.DUP6,
    values.DUP7: mnemonics.DUP7,
    values.DUP8: mnemonics.DUP8,
    values.DUP9: mnemonics.DUP9,
    values.DUP10: mnemonics.DUP10,
    values.DUP11: mnemonics.DUP11,
    values.DUP12: mnemonics.DUP12,
    values.DUP13: mnemonics.DUP13,
    values.DUP14: mnemonics.DUP14,
    values.DUP15: mnemonics.DUP15,
    values.DUP16: mnemonics.DUP16,
    #
    # Exchange Operations
    #
    values.SWAP1: mnemonics.SWAP1,
    values.SWAP2: mnemonics.SWAP2,
    values.SWAP3: mnemonics.SWAP3,
    values.SWAP4: mnemonics.SWAP4,
    values.SWAP5: mnemonics.SWAP5,
    values.SWAP6: mnemonics.SWAP6,
    values.SWAP7: mnemonics.SWAP7,
    values.SWAP8: mnemonics.SWAP8,
    values.SWAP9: mnemonics.SWAP9,
    values.SWAP10: mnemonics.SWAP10,
    values.SWAP11: mnemonics.SWAP11,
    values.SWAP12: mnemonics.SWAP12,
    values.SWAP13: mnemonics.SWAP13,
    values.SWAP14: mnemonics.SWAP14,
    values.SWAP15: mnemonics.SWAP15,
    values.SWAP16: mnemonics.SWAP16,
    #
    # Logging
    #
    values.LOG0: mnemonics.LOG0,
    values.LOG1: mnemonics.LOG1,
    values.LOG2: mnemonics.LOG2,
    values.LOG3: mnemonics.LOG3,
    values.LOG4: mnemonics.LOG4,
    #
    # System
    #
    values.CREATE: mnemonics.CREATE,
    values.CALL: mnemonics.CALL,
    values.CALLCODE: mnemonics.CALLCODE,
    values.RETURN: mnemonics.RETURN,
    values.DELEGATECALL: mnemonics.DELEGATECALL,
    values.SUICIDE: mnemonics.SUICIDE,
}
