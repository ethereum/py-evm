from typing import (
    Tuple,
)

from eth_typing import (
    Address,
)
import rlp
from rlp.sedes import (
    big_endian_int,
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
from eth.rlp.sedes import (
    address,
)
from eth.vm import (
    mnemonics,
)
from eth.vm.forks.berlin.logic import (
    CallCodeEIP2929,
    CallEIP2929,
    DelegateCallEIP2929,
    LoadFeeByCacheWarmth,
    StaticCallEIP2929,
    _consume_gas_for_account_load,
)
from eth.vm.logic.call import (
    BaseCall,
)
from eth.vm.logic.context import (
    consume_extcodecopy_word_cost,
)

from .constants import (
    DELEGATION_DESIGNATION,
)

CallParams = Tuple[int, int, Address, Address, Address, int, int, int, int, bool, bool]


def extcodesize_eip7702(computation: ComputationAPI) -> None:
    first_bytestring = computation.stack_pop1_bytes()
    if first_bytestring[:3] == DELEGATION_DESIGNATION:
        address = force_bytes_to_address(first_bytestring[3:])
    else:
        address = force_bytes_to_address(first_bytestring)

    _consume_gas_for_account_load(computation, address, mnemonics.EXTCODEHASH)

    code_size = len(first_bytestring)
    computation.stack_push_int(code_size)


def extcodehash_eip7702(computation: ComputationAPI) -> None:
    """
    Return the code hash for a given address.
    EIP: https://github.com/ethereum/EIPs/blob/master/EIPS/eip-1052.md
    """
    state = computation.state
    first_bytestring = computation.stack_pop1_bytes()
    if first_bytestring[:3] == DELEGATION_DESIGNATION:
        address = force_bytes_to_address(first_bytestring[3:])

        _consume_gas_for_account_load(computation, address, mnemonics.EXTCODEHASH)

        if state.account_is_empty(address):
            computation.stack_push_bytes(constants.NULL_BYTE)
        else:
            computation.stack_push_bytes(state.get_code_hash(Address(first_bytestring)))

    else:
        address = force_bytes_to_address(first_bytestring)

        _consume_gas_for_account_load(computation, address, mnemonics.EXTCODEHASH)

        if state.account_is_empty(address):
            computation.stack_push_bytes(constants.NULL_BYTE)
        else:
            computation.stack_push_bytes(state.get_code_hash(address))


def extcodecopy_execute_eip7702(
    computation: ComputationAPI, account: Address
) -> Tuple[Address, int]:
    """
    Runs the logical component of extcodecopy, without charging gas.

    :return (target_address, copy_size): useful for the caller to determine gas costs
    """
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
    first_bytestring = computation.stack_pop1_bytes()
    if first_bytestring[:3] == DELEGATION_DESIGNATION:
        account = force_bytes_to_address(first_bytestring[3:])
        address, size = extcodecopy_execute_eip7702(computation, account)
        consume_extcodecopy_word_cost(computation, size)
        _consume_gas_for_account_load(computation, address, mnemonics.EXTCODECOPY)
    else:
        account = force_bytes_to_address(first_bytestring)
        address, size = extcodecopy_execute_eip7702(computation, account)
        consume_extcodecopy_word_cost(computation, size)
        _consume_gas_for_account_load(computation, address, mnemonics.EXTCODECOPY)


class Authorization(rlp.Serializable):
    fields = (
        ("chain_id", big_endian_int),
        ("account", address),
        ("nonce", big_endian_int),
        ("y_parity", big_endian_int),
        ("r", big_endian_int),
        ("s", big_endian_int),
    )

    def __init__(
        self,
        chain_id: int,
        account: Address,
        nonce: int,
        y_parity: int,
        r: int,
        s: int,
    ) -> None:
        super().__init__(
            chain_id=chain_id,
            account=account,
            nonce=nonce,
            y_parity=y_parity,
            r=r,
            s=s,
        )


def _has_delegation_prefix(code: bytes) -> bool:
    return code[:3] == DELEGATION_DESIGNATION


#
# EIP-7702
#
class BaseCallEIP7702(LoadFeeByCacheWarmth, BaseCall):
    def call_eip_7702(self, computation: ComputationAPI) -> None:
        computation.consume_gas(
            self.gas_cost,
            reason=self.mnemonic,
        )

        (
            gas,
            value,
            to,
            sender,
            code_address,
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
            should_transfer_value,
            is_static,
            is_delegation,
        ) = self.get_call_params(computation)

        computation.extend_memory(memory_input_start_position, memory_input_size)
        computation.extend_memory(memory_output_start_position, memory_output_size)

        call_data = computation.memory_read_bytes(
            memory_input_start_position, memory_input_size
        )
        #
        # Message gas allocation and fees
        #
        if code_address:
            code_source = code_address
        else:
            code_source = to
        load_account_fee = self.get_account_load_fee(computation, code_source)
        if load_account_fee > 0:
            computation.consume_gas(
                load_account_fee,
                reason=f"{self.mnemonic} charges implicit account load for reading code",  # noqa: E501
            )
            if self.logger.show_debug2:
                self.logger.debug2(
                    f"{self.mnemonic} is charged {load_account_fee} for invoking "
                    f"code at account 0x{code_source.hex()}"
                )

        # This must be computed *after* the load account fee is charged, so
        # that the 63/64ths rule is applied against the reduced remaining gas.
        child_msg_gas, child_msg_gas_fee = self.compute_msg_gas(
            computation, gas, to, value
        )
        computation.consume_gas(child_msg_gas_fee, reason=self.mnemonic)

        # Pre-call checks
        sender_balance = computation.state.get_balance(computation.msg.storage_address)

        insufficient_funds = should_transfer_value and sender_balance < value
        stack_too_deep = computation.msg.depth + 1 > constants.STACK_DEPTH_LIMIT

        if insufficient_funds or stack_too_deep:
            computation.return_data = b""
            if insufficient_funds:
                err_message = (
                    f"Insufficient Funds: have: {sender_balance} | need: {value}"
                )
            elif stack_too_deep:
                err_message = "Stack Limit Reached"
            else:
                raise Exception("Invariant: Unreachable code path")

            self.logger.debug2(f"{self.mnemonic} failure: {err_message}")
            computation.return_gas(child_msg_gas)
            computation.stack_push_int(0)
        else:
            if is_delegation:
                if code_address in computation.precompiles:
                    code = b""
                else:
                    code = computation.state.get_code(code_address)

                delegation_fee = self.get_account_load_fee(computation, code_address)
                if delegation_fee > 0:
                    computation.consume_gas(delegation_fee, reason="delegation fee")
            else:
                code = computation.state.get_code(to)

            child_msg_kwargs = {
                "gas": child_msg_gas,
                "value": value,
                "to": to,
                "data": call_data,
                "code": code,
                "code_address": code_address,
                "should_transfer_value": should_transfer_value,
                "is_static": is_static,
                "is_delegation": is_delegation,
            }

            if sender is not None:
                child_msg_kwargs["sender"] = sender

            # TODO: after upgrade to py3.6, use a TypedDict and try again
            child_msg = computation.prepare_child_message(**child_msg_kwargs)  # type: ignore  # noqa: E501

            child_computation = computation.apply_child_computation(child_msg)

            if child_computation.is_error:
                computation.stack_push_int(0)
            else:
                computation.stack_push_int(1)

            if not child_computation.should_erase_return_data:
                actual_output_size = min(
                    memory_output_size, len(child_computation.output)
                )
                computation.memory_write(
                    memory_output_start_position,
                    actual_output_size,
                    child_computation.output[:actual_output_size],
                )

            if child_computation.should_return_gas:
                computation.return_gas(child_computation.get_gas_remaining())


class CallEIP7702(CallEIP2929, BaseCallEIP7702):
    def get_call_params(self, computation: ComputationAPI) -> CallParams:
        # print("******************* callEIP7702 *********************")
        gas = computation.stack_pop1_int()
        address = force_bytes_to_address(computation.stack_pop1_bytes())
        code = computation.state.get_code(address)
        if code[:3] == DELEGATION_DESIGNATION:
            code_address = force_bytes_to_address(code[3:])
            is_delegation = True
        else:
            code_address = address
            is_delegation = False

        (
            value,
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
        ) = computation.stack_pop_ints(5)

        to = computation.msg.storage_address
        sender = computation.msg.storage_address

        return (
            gas,
            value,
            to,
            sender,
            code_address,
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
            True,  # should_transfer_value,
            computation.msg.is_static,
            is_delegation,
        )

    def __call__(self, computation: ComputationAPI) -> None:
        self.call_eip_7702(computation)


class CallCodeEIP7702(CallCodeEIP2929, BaseCallEIP7702):
    def get_call_params(self, computation: ComputationAPI) -> CallParams:
        print("******************* CallCodeEIP7702 *********************")
        gas = computation.stack_pop1_int()
        address = force_bytes_to_address(computation.stack_pop1_bytes())
        code = computation.state.get_code(address)
        if code[:3] == DELEGATION_DESIGNATION:
            code_address = force_bytes_to_address(code[3:])
            is_delegation = True
        else:
            code_address = address
            is_delegation = False

        (
            value,
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
        ) = computation.stack_pop_ints(5)

        to = computation.msg.storage_address
        sender = computation.msg.storage_address

        return (
            gas,
            value,
            to,
            sender,
            code_address,
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
            True,  # should_transfer_value,
            computation.msg.is_static,
            is_delegation,
        )

    def __call__(self, computation: ComputationAPI) -> None:
        self.call_eip_7702(computation)


class DelegateCallEIP7702(DelegateCallEIP2929, BaseCallEIP7702):
    def get_call_params(self, computation: ComputationAPI) -> CallParams:
        print("******************* DelegateCallEIP7702 *********************")
        gas = computation.stack_pop1_int()
        address = force_bytes_to_address(computation.stack_pop1_bytes())
        code = computation.state.get_code(address)
        if code[:3] == DELEGATION_DESIGNATION:
            code_address = force_bytes_to_address(code[3:])
            is_delegation = True
        else:
            code_address = address
            is_delegation = False

        (
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
        ) = computation.stack_pop_ints(4)

        to = computation.msg.storage_address
        sender = computation.msg.sender
        value = computation.msg.value

        return (
            gas,
            value,
            to,
            sender,
            code_address,
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
            False,  # should_transfer_value,
            computation.msg.is_static,
            is_delegation,
        )

    def __call__(self, computation: ComputationAPI) -> None:
        self.call_eip_7702(computation)


class StaticCallEIP7702(StaticCallEIP2929, BaseCallEIP7702):
    def get_call_params(self, computation: ComputationAPI) -> CallParams:
        print("******************* StaticCallEIP7702 *********************")
        gas = computation.stack_pop1_int()
        address = force_bytes_to_address(computation.stack_pop1_bytes())
        code = computation.state.get_code(address)
        if code[:3] == DELEGATION_DESIGNATION:
            to = force_bytes_to_address(code[3:])
            is_delegation = True
        else:
            to = address
            is_delegation = False

        (
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
        ) = computation.stack_pop_ints(4)

        return (
            gas,
            0,  # value
            to,
            None,  # sender
            None,  # code_address
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
            False,  # should_transfer_value,
            True,  # is_static
            is_delegation,
        )

    def __call__(self, computation: ComputationAPI) -> None:
        self.call_eip_7702(computation)
