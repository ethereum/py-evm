from evm import opcodes

from evm.logic import (
    arithmetic,
    comparison,
    context,
    duplication,
    flow,
    memory,
    sha3,
    stack,
    storage,
    swap,
    system,
)


def not_implemented(name):
    def fn(*args, **kwargs):
        raise NotImplementedError("The {0} opcode has not been implemented".format(name))
    return fn


OPCODE_LOGIC_FUNCTIONS = {
    #
    # Arithmetic
    #
    opcodes.STOP: flow.stop,
    opcodes.ADD: arithmetic.add,
    opcodes.MUL: arithmetic.mul,
    opcodes.SUB: arithmetic.sub,
    opcodes.DIV: arithmetic.div,
    opcodes.SDIV: arithmetic.sdiv,
    opcodes.MOD: arithmetic.mod,
    opcodes.SMOD: arithmetic.smod,
    opcodes.ADDMOD: arithmetic.addmod,
    opcodes.MULMOD: arithmetic.mulmod,
    opcodes.EXP: arithmetic.exp,
    opcodes.SIGNEXTEND: arithmetic.signextend,
    #
    # Comparisons
    #
    opcodes.LT: comparison.lt,
    opcodes.GT: comparison.gt,
    opcodes.SLT: comparison.slt,
    opcodes.SGT: comparison.sgt,
    opcodes.EQ: comparison.eq,
    opcodes.ISZERO: comparison.iszero,
    opcodes.AND: comparison.and_op,
    opcodes.OR: comparison.or_op,
    opcodes.XOR: comparison.xor,
    opcodes.NOT: comparison.not_op,
    opcodes.BYTE: comparison.byte_op,
    #
    # Sha3
    #
    opcodes.SHA3: sha3.sha3,
    #
    # Environment Information
    #
    opcodes.ADDRESS: not_implemented('ADDRESS'),  # TODO: implement me
    opcodes.BALANCE: not_implemented('BALANCE'),  # TODO: implement me
    opcodes.ORIGIN: not_implemented('ORIGIN'),  # TODO: implement me
    opcodes.CALLER: not_implemented('CALLER'),  # TODO: implement me
    opcodes.CALLVALUE: not_implemented('CALLVALUE'),  # TODO: implement me
    opcodes.CALLDATALOAD: context.calldataload,
    opcodes.CALLDATASIZE: not_implemented('CALLDATASIZE'),  # TODO: implement me
    opcodes.CALLDATACOPY: not_implemented('CALLDATACOPY'),  # TODO: implement me
    opcodes.CODESIZE: not_implemented('CODESIZE'),  # TODO: implement me
    opcodes.CODECOPY: not_implemented('CODECOPY'),  # TODO: implement me
    opcodes.GASPRICE: not_implemented('GASPRICE'),  # TODO: implement me
    opcodes.EXTCODESIZE: not_implemented('EXTCODESIZE'),  # TODO: implement me
    opcodes.EXTCODECOPY: not_implemented('EXTCODECOPY'),  # TODO: implement me
    #
    # Block Information
    #
    opcodes.BLOCKHASH: not_implemented('BLOCKHASH'),  # TODO: implement me
    opcodes.COINBASE: not_implemented('COINBASE'),  # TODO: implement me
    opcodes.TIMESTAMP: not_implemented('TIMESTAMP'),  # TODO: implement me
    opcodes.NUMBER: not_implemented('NUMBER'),  # TODO: implement me
    opcodes.DIFFICULTY: not_implemented('DIFFICULTY'),  # TODO: implement me
    opcodes.GASLIMIT: not_implemented('GASLIMIT'),  # TODO: implement me
    #
    # Stack, Memory, Storage and Flow Operations
    #
    opcodes.POP: stack.pop,
    opcodes.MLOAD: memory.mload,
    opcodes.MSTORE: memory.mstore,
    opcodes.MSTORE8: memory.mstore8,
    opcodes.SLOAD: storage.sload,
    opcodes.SSTORE: storage.sstore,
    opcodes.JUMP: flow.jump,
    opcodes.JUMPI: flow.jumpi,
    opcodes.PC: not_implemented('PC'),  # TODO: implement me
    opcodes.MSIZE: not_implemented('MSIZE'),  # TODO: implement me
    opcodes.GAS: not_implemented('GAS'),  # TODO: implement me
    opcodes.JUMPDEST: flow.jumpdest,
    #
    # Push Operations
    #
    opcodes.PUSH1: stack.push1,
    opcodes.PUSH2: stack.push2,
    opcodes.PUSH3: stack.push3,
    opcodes.PUSH4: stack.push4,
    opcodes.PUSH5: stack.push5,
    opcodes.PUSH6: stack.push6,
    opcodes.PUSH7: stack.push7,
    opcodes.PUSH8: stack.push8,
    opcodes.PUSH9: stack.push9,
    opcodes.PUSH10: stack.push10,
    opcodes.PUSH11: stack.push11,
    opcodes.PUSH12: stack.push12,
    opcodes.PUSH13: stack.push13,
    opcodes.PUSH14: stack.push14,
    opcodes.PUSH15: stack.push15,
    opcodes.PUSH16: stack.push16,
    opcodes.PUSH17: stack.push17,
    opcodes.PUSH18: stack.push18,
    opcodes.PUSH19: stack.push19,
    opcodes.PUSH20: stack.push20,
    opcodes.PUSH21: stack.push21,
    opcodes.PUSH22: stack.push22,
    opcodes.PUSH23: stack.push23,
    opcodes.PUSH24: stack.push24,
    opcodes.PUSH25: stack.push25,
    opcodes.PUSH26: stack.push26,
    opcodes.PUSH27: stack.push27,
    opcodes.PUSH28: stack.push28,
    opcodes.PUSH29: stack.push29,
    opcodes.PUSH30: stack.push30,
    opcodes.PUSH31: stack.push31,
    opcodes.PUSH32: stack.push32,
    #
    # Duplicate Operations
    #
    opcodes.DUP1: duplication.dup1,
    opcodes.DUP2: duplication.dup2,
    opcodes.DUP3: duplication.dup3,
    opcodes.DUP4: duplication.dup4,
    opcodes.DUP5: duplication.dup5,
    opcodes.DUP6: duplication.dup6,
    opcodes.DUP7: duplication.dup7,
    opcodes.DUP8: duplication.dup8,
    opcodes.DUP9: duplication.dup9,
    opcodes.DUP10: duplication.dup10,
    opcodes.DUP11: duplication.dup11,
    opcodes.DUP12: duplication.dup12,
    opcodes.DUP13: duplication.dup13,
    opcodes.DUP14: duplication.dup14,
    opcodes.DUP15: duplication.dup15,
    opcodes.DUP16: duplication.dup16,
    #
    # Exchange Operations
    #
    opcodes.SWAP1: swap.swap1,
    opcodes.SWAP2: swap.swap2,
    opcodes.SWAP3: swap.swap3,
    opcodes.SWAP4: swap.swap4,
    opcodes.SWAP5: swap.swap5,
    opcodes.SWAP6: swap.swap6,
    opcodes.SWAP7: swap.swap7,
    opcodes.SWAP8: swap.swap8,
    opcodes.SWAP9: swap.swap9,
    opcodes.SWAP10: swap.swap10,
    opcodes.SWAP11: swap.swap11,
    opcodes.SWAP12: swap.swap12,
    opcodes.SWAP13: swap.swap13,
    opcodes.SWAP14: swap.swap14,
    opcodes.SWAP15: swap.swap15,
    opcodes.SWAP16: swap.swap16,
    #
    # Logging
    #
    opcodes.LOG0: not_implemented('LOG0'),  # TODO: implement me
    opcodes.LOG1: not_implemented('LOG1'),  # TODO: implement me
    opcodes.LOG2: not_implemented('LOG2'),  # TODO: implement me
    opcodes.LOG3: not_implemented('LOG3'),  # TODO: implement me
    opcodes.LOG4: not_implemented('LOG4'),  # TODO: implement me
    #
    # System
    #
    opcodes.CREATE: not_implemented('CREATE'),  # TODO: implement me
    opcodes.CALL: not_implemented('CALL'),  # TODO: implement me
    opcodes.CALLCODE: not_implemented('CALLCODE'),  # TODO: implement me
    opcodes.RETURN: system.return_op,
    opcodes.DELEGATECALL: not_implemented('DELEGATECALL'),  # TODO: implement me
    opcodes.SUICIDE: system.suicide,
}
