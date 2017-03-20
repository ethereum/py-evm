from evm.opcodes import (
    values as opcode_values,
)

from evm.logic import (
    arithmetic,
    comparison,
    duplication,
    environment,
    flow,
    memory,
    push,
    stack,
    storage,
    swap,
    system,
)


def not_implemented(name):
    def fn(*args, **kwargs):
        raise NotImplementedError("The {0} opcode has not been implemented".format(name))
    return fn


OPCODE_LOOKUP = {
    #
    # Arithmetic
    #
    opcode_values.STOP: flow.stop,
    opcode_values.ADD: arithmetic.add,
    opcode_values.MUL: arithmetic.mul,
    opcode_values.SUB: arithmetic.sub,
    opcode_values.DIV: arithmetic.div,
    opcode_values.SDIV: arithmetic.sdiv,
    opcode_values.MOD: arithmetic.mod,
    opcode_values.SMOD: arithmetic.smod,
    opcode_values.ADDMOD: arithmetic.addmod,
    opcode_values.MULMOD: arithmetic.mulmod,
    opcode_values.EXP: arithmetic.exp,
    opcode_values.SIGNEXTEND: arithmetic.signextend,
    #
    # Comparisons
    #
    opcode_values.LT: comparison.lt,
    opcode_values.GT: comparison.gt,
    opcode_values.SLT: comparison.slt,
    opcode_values.SGT: comparison.sgt,
    opcode_values.EQ: comparison.eq,
    opcode_values.ISZERO: comparison.iszero,
    opcode_values.AND: comparison.and_op,
    opcode_values.OR: comparison.or_op,
    opcode_values.XOR: comparison.xor,
    opcode_values.NOT: comparison.not_op,
    opcode_values.BYTE: comparison.byte_op,
    #
    # Sha3
    #
    opcode_values.SHA3: not_implemented('SHA3'),  # TODO: implement me
    #
    # Environment Information
    #
    opcode_values.ADDRESS: not_implemented('ADDRESS'),  # TODO: implement me
    opcode_values.BALANCE: not_implemented('BALANCE'),  # TODO: implement me
    opcode_values.ORIGIN: not_implemented('ORIGIN'),  # TODO: implement me
    opcode_values.CALLER: not_implemented('CALLER'),  # TODO: implement me
    opcode_values.CALLVALUE: not_implemented('CALLVALUE'),  # TODO: implement me
    opcode_values.CALLDATALOAD: environment.calldataload,
    opcode_values.CALLDATASIZE: not_implemented('CALLDATASIZE'),  # TODO: implement me
    opcode_values.CALLDATACOPY: not_implemented('CALLDATACOPY'),  # TODO: implement me
    opcode_values.CODESIZE: not_implemented('CODESIZE'),  # TODO: implement me
    opcode_values.CODECOPY: not_implemented('CODECOPY'),  # TODO: implement me
    opcode_values.GASPRICE: not_implemented('GASPRICE'),  # TODO: implement me
    opcode_values.EXTCODESIZE: not_implemented('EXTCODESIZE'),  # TODO: implement me
    opcode_values.EXTCODECOPY: not_implemented('EXTCODECOPY'),  # TODO: implement me
    #
    # Block Information
    #
    opcode_values.BLOCKHASH: not_implemented('BLOCKHASH'),  # TODO: implement me
    opcode_values.COINBASE: not_implemented('COINBASE'),  # TODO: implement me
    opcode_values.TIMESTAMP: not_implemented('TIMESTAMP'),  # TODO: implement me
    opcode_values.NUMBER: not_implemented('NUMBER'),  # TODO: implement me
    opcode_values.DIFFICULTY: not_implemented('DIFFICULTY'),  # TODO: implement me
    opcode_values.GASLIMIT: not_implemented('GASLIMIT'),  # TODO: implement me
    #
    # Stack, Memory, Storage and Flow Operations
    #
    opcode_values.POP: stack.pop,
    opcode_values.MLOAD: memory.mload,
    opcode_values.MSTORE: memory.mstore,
    opcode_values.MSTORE8: memory.mstore8,
    opcode_values.SLOAD: storage.sload,
    opcode_values.SSTORE: storage.sstore,
    opcode_values.JUMP: flow.jump,
    opcode_values.JUMPI: flow.jumpi,
    opcode_values.PC: not_implemented('PC'),  # TODO: implement me
    opcode_values.MSIZE: not_implemented('MSIZE'),  # TODO: implement me
    opcode_values.GAS: not_implemented('GAS'),  # TODO: implement me
    opcode_values.JUMPDEST: flow.jumpdest,
    #
    # Push Operations
    #
    opcode_values.PUSH1: push.push1,
    opcode_values.PUSH2: push.push2,
    opcode_values.PUSH3: push.push3,
    opcode_values.PUSH4: push.push4,
    opcode_values.PUSH5: push.push5,
    opcode_values.PUSH6: push.push6,
    opcode_values.PUSH7: push.push7,
    opcode_values.PUSH8: push.push8,
    opcode_values.PUSH9: push.push9,
    opcode_values.PUSH10: push.push10,
    opcode_values.PUSH11: push.push11,
    opcode_values.PUSH12: push.push12,
    opcode_values.PUSH13: push.push13,
    opcode_values.PUSH14: push.push14,
    opcode_values.PUSH15: push.push15,
    opcode_values.PUSH16: push.push16,
    opcode_values.PUSH17: push.push17,
    opcode_values.PUSH18: push.push18,
    opcode_values.PUSH19: push.push19,
    opcode_values.PUSH20: push.push20,
    opcode_values.PUSH21: push.push21,
    opcode_values.PUSH22: push.push22,
    opcode_values.PUSH23: push.push23,
    opcode_values.PUSH24: push.push24,
    opcode_values.PUSH25: push.push25,
    opcode_values.PUSH26: push.push26,
    opcode_values.PUSH27: push.push27,
    opcode_values.PUSH28: push.push28,
    opcode_values.PUSH29: push.push29,
    opcode_values.PUSH30: push.push30,
    opcode_values.PUSH31: push.push31,
    opcode_values.PUSH32: push.push32,
    #
    # Duplicate Operations
    #
    opcode_values.DUP1: duplication.dup1,
    opcode_values.DUP2: duplication.dup2,
    opcode_values.DUP3: duplication.dup3,
    opcode_values.DUP4: duplication.dup4,
    opcode_values.DUP5: duplication.dup5,
    opcode_values.DUP6: duplication.dup6,
    opcode_values.DUP7: duplication.dup7,
    opcode_values.DUP8: duplication.dup8,
    opcode_values.DUP9: duplication.dup9,
    opcode_values.DUP10: duplication.dup10,
    opcode_values.DUP11: duplication.dup11,
    opcode_values.DUP12: duplication.dup12,
    opcode_values.DUP13: duplication.dup13,
    opcode_values.DUP14: duplication.dup14,
    opcode_values.DUP15: duplication.dup15,
    opcode_values.DUP16: duplication.dup16,
    #
    # Exchange Operations
    #
    opcode_values.SWAP1: swap.swap1,
    opcode_values.SWAP2: swap.swap2,
    opcode_values.SWAP3: swap.swap3,
    opcode_values.SWAP4: swap.swap4,
    opcode_values.SWAP5: swap.swap5,
    opcode_values.SWAP6: swap.swap6,
    opcode_values.SWAP7: swap.swap7,
    opcode_values.SWAP8: swap.swap8,
    opcode_values.SWAP9: swap.swap9,
    opcode_values.SWAP10: swap.swap10,
    opcode_values.SWAP11: swap.swap11,
    opcode_values.SWAP12: swap.swap12,
    opcode_values.SWAP13: swap.swap13,
    opcode_values.SWAP14: swap.swap14,
    opcode_values.SWAP15: swap.swap15,
    opcode_values.SWAP16: swap.swap16,
    #
    # Logging
    #
    opcode_values.LOG0: not_implemented('LOG0'),  # TODO: implement me
    opcode_values.LOG1: not_implemented('LOG1'),  # TODO: implement me
    opcode_values.LOG2: not_implemented('LOG2'),  # TODO: implement me
    opcode_values.LOG3: not_implemented('LOG3'),  # TODO: implement me
    opcode_values.LOG4: not_implemented('LOG4'),  # TODO: implement me
    #
    # System
    #
    opcode_values.CREATE: not_implemented('CREATE'),  # TODO: implement me
    opcode_values.CALL: not_implemented('CALL'),  # TODO: implement me
    opcode_values.CALLCODE: not_implemented('CALLCODE'),  # TODO: implement me
    opcode_values.RETURN: system.return_op,
    opcode_values.DELEGATECALL: not_implemented('DELEGATECALL'),  # TODO: implement me
    opcode_values.SUICIDE: not_implemented('SUICIDE'),  # TODO: implement me
}
