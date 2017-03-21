from evm import constants
from evm import opcodes

from evm.utils.numeric import (
    ceil32,
    big_endian_to_int,
)


def memory_gas_cost(size_in_bytes):
    size_in_words = ceil32(size_in_bytes) // 32
    linear_cost = size_in_words * constants.GAS_MEMORY
    quadratic_cost = size_in_words ** 2 // constants.GAS_MEMORY_QUADRATIC_DENOMINATOR

    total_cost = linear_cost + quadratic_cost
    return total_cost


def mem_extend(mem, compustate, op, start, sz):
    if sz:
        oldsize = len(mem) // 32
        old_totalfee = oldsize * opcodes.GMEMORY + \
            oldsize ** 2 // opcodes.GQUADRATICMEMDENOM
        newsize = utils.ceil32(start + sz) // 32
        # if newsize > 524288:
        #     raise Exception("Memory above 16 MB per call not supported by this VM")
        new_totalfee = newsize * opcodes.GMEMORY + \
            newsize ** 2 // opcodes.GQUADRATICMEMDENOM
        if old_totalfee < new_totalfee:
            memfee = new_totalfee - old_totalfee
            if compustate.gas < memfee:
                compustate.gas = 0
                return False
            compustate.gas -= memfee
            m_extend = (newsize - oldsize) * 32
            mem.extend([0] * m_extend)
    return True


def sstore_gas_cost(current_value, value_to_write):
    value_as_int = big_endian_to_int(value_to_write)
    if current_value:
        gas_cost = constants.GAS_SRESET if value_as_int else constants.GAS_SRESET
        gas_refund = constants.REFUND_SCLEAR if value_as_int else 0
    else:
        gas_cost = constants.GAS_SSET if value_as_int else constants.GAS_SRESET
        gas_refund = 0
    return gas_cost, gas_refund


def call_gas_cost(to, value, gas):
    transfer_gas_cost = constants.GAS_CALLVALUE if value else 0
    create_gas_cost = constants.GAS_CREATE if to == constants.ZERO_ADDRESS else 0

    extra_gas = constants.GAS_CALL + transfer_gas_cost + create_gas_cost

    total_gas_cost = gas + extra_gas

    return total_gas_cost


OPCODE_GAS_COSTS = {
    #
    # Arithmetic
    #
    opcodes.STOP: constants.GAS_ZERO,
    opcodes.ADD: constants.GAS_VERYLOW,
    opcodes.MUL: constants.GAS_LOW,
    opcodes.SUB: constants.GAS_VERYLOW,
    opcodes.DIV: constants.GAS_LOW,
    opcodes.SDIV: constants.GAS_LOW,
    opcodes.MOD: constants.GAS_LOW,
    opcodes.SMOD: constants.GAS_LOW,
    opcodes.ADDMOD: constants.GAS_MID,
    opcodes.MULMOD: constants.GAS_MID,
    opcodes.EXP: constants.GAS_EXP,
    opcodes.SIGNEXTEND: constants.GAS_LOW,
    #
    # Comparisons
    #
    opcodes.LT: constants.GAS_VERYLOW,
    opcodes.GT: constants.GAS_VERYLOW,
    opcodes.SLT: constants.GAS_VERYLOW,
    opcodes.SGT: constants.GAS_VERYLOW,
    opcodes.EQ: constants.GAS_VERYLOW,
    opcodes.ISZERO: constants.GAS_VERYLOW,
    opcodes.AND: constants.GAS_VERYLOW,
    opcodes.OR: constants.GAS_VERYLOW,
    opcodes.XOR: constants.GAS_VERYLOW,
    opcodes.NOT: constants.GAS_VERYLOW,
    opcodes.BYTE: constants.GAS_VERYLOW,
    #
    # Sha3
    #
    opcodes.SHA3: constants.GAS_SHA3,
    #
    # Environment Information
    #
    opcodes.ADDRESS: constants.GAS_BASE,
    opcodes.BALANCE: constants.GAS_BALANCE,
    opcodes.ORIGIN: constants.GAS_BASE,
    opcodes.CALLER: constants.GAS_BASE,
    opcodes.CALLVALUE: constants.GAS_BASE,
    opcodes.CALLDATALOAD: constants.GAS_VERYLOW,
    opcodes.CALLDATASIZE: constants.GAS_BASE,
    opcodes.CALLDATACOPY: constants.GAS_VERYLOW,
    opcodes.CODESIZE: constants.GAS_BASE,
    opcodes.CODECOPY: constants.GAS_VERYLOW,
    opcodes.GASPRICE: constants.GAS_BASE,
    opcodes.EXTCODESIZE: constants.GAS_EXTCODE,
    opcodes.EXTCODECOPY: constants.GAS_EXTCODE,
    #
    # Block Information
    #
    opcodes.BLOCKHASH: constants.GAS_BLOCKHASH,
    opcodes.COINBASE: constants.GAS_BASE,
    opcodes.TIMESTAMP: constants.GAS_BASE,
    opcodes.NUMBER: constants.GAS_BASE,
    opcodes.DIFFICULTY: constants.GAS_BASE,
    opcodes.GASLIMIT: constants.GAS_BASE,
    #
    # Stack, Memory, Storage and Flow Operations
    #
    opcodes.POP: constants.GAS_BASE,
    opcodes.MLOAD: constants.GAS_VERYLOW,
    opcodes.MSTORE: constants.GAS_VERYLOW,
    opcodes.MSTORE8: constants.GAS_VERYLOW,
    opcodes.SLOAD: constants.GAS_SLOAD,
    opcodes.SSTORE: constants.GAS_NULL,
    opcodes.JUMP: constants.GAS_MID,
    opcodes.JUMPI: constants.GAS_HIGH,
    opcodes.PC: constants.GAS_BASE,
    opcodes.MSIZE: constants.GAS_BASE,
    opcodes.GAS: constants.GAS_BASE,
    opcodes.JUMPDEST: constants.GAS_JUMPDEST,
    #
    # Push Operations
    #
    opcodes.PUSH1: constants.GAS_VERYLOW,
    opcodes.PUSH2: constants.GAS_VERYLOW,
    opcodes.PUSH3: constants.GAS_VERYLOW,
    opcodes.PUSH4: constants.GAS_VERYLOW,
    opcodes.PUSH5: constants.GAS_VERYLOW,
    opcodes.PUSH6: constants.GAS_VERYLOW,
    opcodes.PUSH7: constants.GAS_VERYLOW,
    opcodes.PUSH8: constants.GAS_VERYLOW,
    opcodes.PUSH9: constants.GAS_VERYLOW,
    opcodes.PUSH10: constants.GAS_VERYLOW,
    opcodes.PUSH11: constants.GAS_VERYLOW,
    opcodes.PUSH12: constants.GAS_VERYLOW,
    opcodes.PUSH13: constants.GAS_VERYLOW,
    opcodes.PUSH14: constants.GAS_VERYLOW,
    opcodes.PUSH15: constants.GAS_VERYLOW,
    opcodes.PUSH16: constants.GAS_VERYLOW,
    opcodes.PUSH17: constants.GAS_VERYLOW,
    opcodes.PUSH18: constants.GAS_VERYLOW,
    opcodes.PUSH19: constants.GAS_VERYLOW,
    opcodes.PUSH20: constants.GAS_VERYLOW,
    opcodes.PUSH21: constants.GAS_VERYLOW,
    opcodes.PUSH22: constants.GAS_VERYLOW,
    opcodes.PUSH23: constants.GAS_VERYLOW,
    opcodes.PUSH24: constants.GAS_VERYLOW,
    opcodes.PUSH25: constants.GAS_VERYLOW,
    opcodes.PUSH26: constants.GAS_VERYLOW,
    opcodes.PUSH27: constants.GAS_VERYLOW,
    opcodes.PUSH28: constants.GAS_VERYLOW,
    opcodes.PUSH29: constants.GAS_VERYLOW,
    opcodes.PUSH30: constants.GAS_VERYLOW,
    opcodes.PUSH31: constants.GAS_VERYLOW,
    opcodes.PUSH32: constants.GAS_VERYLOW,
    #
    # Duplicate Operations
    #
    opcodes.DUP1: constants.GAS_VERYLOW,
    opcodes.DUP2: constants.GAS_VERYLOW,
    opcodes.DUP3: constants.GAS_VERYLOW,
    opcodes.DUP4: constants.GAS_VERYLOW,
    opcodes.DUP5: constants.GAS_VERYLOW,
    opcodes.DUP6: constants.GAS_VERYLOW,
    opcodes.DUP7: constants.GAS_VERYLOW,
    opcodes.DUP8: constants.GAS_VERYLOW,
    opcodes.DUP9: constants.GAS_VERYLOW,
    opcodes.DUP10: constants.GAS_VERYLOW,
    opcodes.DUP11: constants.GAS_VERYLOW,
    opcodes.DUP12: constants.GAS_VERYLOW,
    opcodes.DUP13: constants.GAS_VERYLOW,
    opcodes.DUP14: constants.GAS_VERYLOW,
    opcodes.DUP15: constants.GAS_VERYLOW,
    opcodes.DUP16: constants.GAS_VERYLOW,
    #
    # Exchange Operations
    #
    opcodes.SWAP1: constants.GAS_VERYLOW,
    opcodes.SWAP2: constants.GAS_VERYLOW,
    opcodes.SWAP3: constants.GAS_VERYLOW,
    opcodes.SWAP4: constants.GAS_VERYLOW,
    opcodes.SWAP5: constants.GAS_VERYLOW,
    opcodes.SWAP6: constants.GAS_VERYLOW,
    opcodes.SWAP7: constants.GAS_VERYLOW,
    opcodes.SWAP8: constants.GAS_VERYLOW,
    opcodes.SWAP9: constants.GAS_VERYLOW,
    opcodes.SWAP10: constants.GAS_VERYLOW,
    opcodes.SWAP11: constants.GAS_VERYLOW,
    opcodes.SWAP12: constants.GAS_VERYLOW,
    opcodes.SWAP13: constants.GAS_VERYLOW,
    opcodes.SWAP14: constants.GAS_VERYLOW,
    opcodes.SWAP15: constants.GAS_VERYLOW,
    opcodes.SWAP16: constants.GAS_VERYLOW,
    #
    # Logging
    #
    opcodes.LOG0: constants.GAS_LOG,
    opcodes.LOG1: constants.GAS_LOG,
    opcodes.LOG2: constants.GAS_LOG,
    opcodes.LOG3: constants.GAS_LOG,
    opcodes.LOG4: constants.GAS_LOG,
    #
    # System
    #
    opcodes.CREATE: constants.GAS_CREATE,
    opcodes.CALL: constants.GAS_CALL,
    opcodes.CALLCODE: constants.GAS_CALL,
    opcodes.RETURN: constants.GAS_ZERO,
    opcodes.DELEGATECALL: constants.GAS_CALL,
    opcodes.SUICIDE: constants.GAS_NULL,
}
