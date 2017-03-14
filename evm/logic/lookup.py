from evm import opcodes

from . import (
    arithmetic,
    storage,
    push,
)


def not_implemented(*args, **kwargs):
    raise NotImplementedError("This opcode has not been implemented")


OPCODE_LOOKUP = {
    #
    # Arithmetic
    #
    opcodes.STOP: not_implemented,  # TODO: implement me
    opcodes.ADD: arithmetic.add,
    opcodes.MUL: not_implemented,  # TODO: implement me
    opcodes.SUB: not_implemented,  # TODO: implement me
    opcodes.DIV: not_implemented,  # TODO: implement me
    opcodes.SDIV: not_implemented,  # TODO: implement me
    opcodes.MOD: not_implemented,  # TODO: implement me
    opcodes.SMOD: not_implemented,  # TODO: implement me
    opcodes.ADDMOD: not_implemented,  # TODO: implement me
    opcodes.MULMOD: not_implemented,  # TODO: implement me
    opcodes.EXP: not_implemented,  # TODO: implement me
    opcodes.SIGNEXTEND: not_implemented,  # TODO: implement me
    #
    # Comparisons
    #
    opcodes.LT: not_implemented,  # TODO: implement me
    opcodes.GT: not_implemented,  # TODO: implement me
    opcodes.SLT: not_implemented,  # TODO: implement me
    opcodes.SGT: not_implemented,  # TODO: implement me
    opcodes.EQ: not_implemented,  # TODO: implement me
    opcodes.ISZERO: not_implemented,  # TODO: implement me
    opcodes.AND: not_implemented,  # TODO: implement me
    opcodes.OR: not_implemented,  # TODO: implement me
    opcodes.XOR: not_implemented,  # TODO: implement me
    opcodes.NOT: not_implemented,  # TODO: implement me
    opcodes.BYTE: not_implemented,  # TODO: implement me
    #
    # Sha3
    #
    opcodes.SHA3: not_implemented,  # TODO: implement me
    #
    # Environment Information
    #
    opcodes.ADDRESS: not_implemented,  # TODO: implement me
    opcodes.BALANCE: not_implemented,  # TODO: implement me
    opcodes.ORIGIN: not_implemented,  # TODO: implement me
    opcodes.CALLER: not_implemented,  # TODO: implement me
    opcodes.CALLVALUE: not_implemented,  # TODO: implement me
    opcodes.CALLDATALOAD: not_implemented,  # TODO: implement me
    opcodes.CALLDATASIZE: not_implemented,  # TODO: implement me
    opcodes.CALLDATACOPY: not_implemented,  # TODO: implement me
    opcodes.CODESIZE: not_implemented,  # TODO: implement me
    opcodes.CODECOPY: not_implemented,  # TODO: implement me
    opcodes.GASPRICE: not_implemented,  # TODO: implement me
    opcodes.EXTCODESIZE: not_implemented,  # TODO: implement me
    opcodes.EXTCODECOPY: not_implemented,  # TODO: implement me
    #
    # Block Information
    #
    opcodes.BLOCKHASH: not_implemented,  # TODO: implement me
    opcodes.COINBASE: not_implemented,  # TODO: implement me
    opcodes.TIMESTAMP: not_implemented,  # TODO: implement me
    opcodes.NUMBER: not_implemented,  # TODO: implement me
    opcodes.DIFFICULTY: not_implemented,  # TODO: implement me
    opcodes.GASLIMIT: not_implemented,  # TODO: implement me
    #
    # Stack, Memory, Storage and Flow Operations
    #
    opcodes.POP: not_implemented,  # TODO: implement me
    opcodes.MLOAD: not_implemented,  # TODO: implement me
    opcodes.MSTORE: not_implemented,  # TODO: implement me
    opcodes.MSTORE8: not_implemented,  # TODO: implement me
    opcodes.SLOAD: not_implemented,  # TODO: implement me
    opcodes.SSTORE: storage.sstore,
    opcodes.JUMP: not_implemented,  # TODO: implement me
    opcodes.JUMP1: not_implemented,  # TODO: implement me
    opcodes.PC: not_implemented,  # TODO: implement me
    opcodes.MSIZE: not_implemented,  # TODO: implement me
    opcodes.GAS: not_implemented,  # TODO: implement me
    opcodes.JUMPDEST: not_implemented,  # TODO: implement me
    #
    # Push Operations
    #
    opcodes.PUSH1: push.push_1,
    opcodes.PUSH2: push.push_2,
    opcodes.PUSH3: push.push_3,
    opcodes.PUSH4: push.push_4,
    opcodes.PUSH5: push.push_5,
    opcodes.PUSH6: push.push_6,
    opcodes.PUSH7: push.push_7,
    opcodes.PUSH8: push.push_8,
    opcodes.PUSH9: push.push_9,
    opcodes.PUSH10: push.push_10,
    opcodes.PUSH11: push.push_11,
    opcodes.PUSH12: push.push_12,
    opcodes.PUSH13: push.push_13,
    opcodes.PUSH14: push.push_14,
    opcodes.PUSH15: push.push_15,
    opcodes.PUSH16: push.push_16,
    opcodes.PUSH17: push.push_17,
    opcodes.PUSH18: push.push_18,
    opcodes.PUSH19: push.push_19,
    opcodes.PUSH20: push.push_20,
    opcodes.PUSH21: push.push_21,
    opcodes.PUSH22: push.push_22,
    opcodes.PUSH23: push.push_23,
    opcodes.PUSH24: push.push_24,
    opcodes.PUSH25: push.push_25,
    opcodes.PUSH26: push.push_26,
    opcodes.PUSH27: push.push_27,
    opcodes.PUSH28: push.push_28,
    opcodes.PUSH29: push.push_29,
    opcodes.PUSH30: push.push_30,
    opcodes.PUSH31: push.push_31,
    opcodes.PUSH32: push.push_32,
    #
    # Duplicate Operations
    #
    opcodes.DUP1: not_implemented,  # TODO: implement me
    opcodes.DUP2: not_implemented,  # TODO: implement me
    opcodes.DUP3: not_implemented,  # TODO: implement me
    opcodes.DUP4: not_implemented,  # TODO: implement me
    opcodes.DUP5: not_implemented,  # TODO: implement me
    opcodes.DUP6: not_implemented,  # TODO: implement me
    opcodes.DUP7: not_implemented,  # TODO: implement me
    opcodes.DUP8: not_implemented,  # TODO: implement me
    opcodes.DUP9: not_implemented,  # TODO: implement me
    opcodes.DUP10: not_implemented,  # TODO: implement me
    opcodes.DUP11: not_implemented,  # TODO: implement me
    opcodes.DUP12: not_implemented,  # TODO: implement me
    opcodes.DUP13: not_implemented,  # TODO: implement me
    opcodes.DUP14: not_implemented,  # TODO: implement me
    opcodes.DUP15: not_implemented,  # TODO: implement me
    opcodes.DUP16: not_implemented,  # TODO: implement me
    #
    # Exchange Operations
    #
    opcodes.SWAP1: not_implemented,  # TODO: implement me
    opcodes.SWAP2: not_implemented,  # TODO: implement me
    opcodes.SWAP3: not_implemented,  # TODO: implement me
    opcodes.SWAP4: not_implemented,  # TODO: implement me
    opcodes.SWAP5: not_implemented,  # TODO: implement me
    opcodes.SWAP6: not_implemented,  # TODO: implement me
    opcodes.SWAP7: not_implemented,  # TODO: implement me
    opcodes.SWAP8: not_implemented,  # TODO: implement me
    opcodes.SWAP9: not_implemented,  # TODO: implement me
    opcodes.SWAP10: not_implemented,  # TODO: implement me
    opcodes.SWAP11: not_implemented,  # TODO: implement me
    opcodes.SWAP12: not_implemented,  # TODO: implement me
    opcodes.SWAP13: not_implemented,  # TODO: implement me
    opcodes.SWAP14: not_implemented,  # TODO: implement me
    opcodes.SWAP15: not_implemented,  # TODO: implement me
    opcodes.SWAP16: not_implemented,  # TODO: implement me
    #
    # Logging
    #
    opcodes.LOG0: not_implemented,  # TODO: implement me
    opcodes.LOG1: not_implemented,  # TODO: implement me
    opcodes.LOG2: not_implemented,  # TODO: implement me
    opcodes.LOG3: not_implemented,  # TODO: implement me
    opcodes.LOG4: not_implemented,  # TODO: implement me
    #
    # System
    #
    opcodes.CREATE: not_implemented,  # TODO: implement me
    opcodes.CALL: not_implemented,  # TODO: implement me
    opcodes.CALLCODE: not_implemented,  # TODO: implement me
    opcodes.RETURN: not_implemented,  # TODO: implement me
    opcodes.DELEGATECALL: not_implemented,  # TODO: implement me
    opcodes.SUICIDE: not_implemented,  # TODO: implement me
}
