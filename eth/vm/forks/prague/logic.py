from typing import (
    Tuple,
)

from eth_typing import (
    Address,
)

from eth import (
    constants,
)
from eth._utils.address import (
    force_bytes_to_address,
)
from eth.abc import (
    ComputationAPI,
)
from eth.vm import (
    mnemonics,
)
from eth.vm.forks.berlin.logic import (
    CallEIP2929,
    _consume_gas_for_account_load,
)
from eth.vm.logic.context import (
    consume_extcodecopy_word_cost,
    extcodecopy_execute,
)

from .constants import (
    DELEGATION_DESIGNATION,
)


def extcodesize_eip7702(computation: ComputationAPI) -> None:
    if computation.stack_pop1_bytes()[:2] == DELEGATION_DESIGNATION:
        address = force_bytes_to_address(computation.stack_pop1_bytes()[2:])
        _consume_gas_for_account_load(computation, address, mnemonics.EXTCODEHASH)

        code_size = len(DELEGATION_DESIGNATION)
        computation.stack_push_int(code_size)

    else:
        address = force_bytes_to_address(computation.stack_pop1_bytes())
        _consume_gas_for_account_load(computation, address, mnemonics.EXTCODEHASH)

        code_size = len(computation.state.get_code(address))
        computation.stack_push_int(code_size)


def extcodehash_eip7702(computation: ComputationAPI) -> None:
    """
    Return the code hash for a given address.
    EIP: https://github.com/ethereum/EIPs/blob/master/EIPS/eip-1052.md
    """
    state = computation.state
    if computation.stack_pop1_bytes()[:2] == DELEGATION_DESIGNATION:
        address = force_bytes_to_address(computation.stack_pop1_bytes()[2:])

        _consume_gas_for_account_load(computation, address, mnemonics.EXTCODEHASH)
        computation.stack_push_bytes(state.get_code_hash(DELEGATION_DESIGNATION))

    else:
        address = force_bytes_to_address(computation.stack_pop1_bytes())

        _consume_gas_for_account_load(computation, address, mnemonics.EXTCODEHASH)

        if state.account_is_empty(address):
            computation.stack_push_bytes(constants.NULL_BYTE)
        else:
            computation.stack_push_bytes(state.get_code_hash(address))


def extcodecopy_execute_eip7702(computation: ComputationAPI) -> Tuple[Address, int]:
    """
    Runs the logical component of extcodecopy, without charging gas.

    :return (target_address, copy_size): useful for the caller to determine gas costs
    """
    account = force_bytes_to_address(computation.stack_pop1_bytes()[2:])
    (
        mem_start_position,
        code_start_position,
        size,
    ) = computation.stack_pop_ints(3)

    computation.extend_memory(mem_start_position, size)

    code = computation.state.get_code(account)

    code_bytes = code[code_start_position : code_start_position + size]
    padded_code_bytes = code_bytes.ljust(size, b"\x00")

    computation.memory_write(mem_start_position, size, padded_code_bytes)

    return account, size


def extcodecopy_eip7702(computation: ComputationAPI) -> None:
    if computation.stack_pop1_bytes()[:2] == DELEGATION_DESIGNATION:
        address, size = extcodecopy_execute_eip7702(computation)
        consume_extcodecopy_word_cost(computation, size)
        # this address might need to be 0xef01
        _consume_gas_for_account_load(computation, address, mnemonics.EXTCODECOPY)
    else:
        address, size = extcodecopy_execute(computation)
        consume_extcodecopy_word_cost(computation, size)
        _consume_gas_for_account_load(computation, address, mnemonics.EXTCODECOPY)


class CallEIP7702(CallEIP2929):
    pass
