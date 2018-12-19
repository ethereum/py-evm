from abc import (
    ABC,
    abstractmethod
)

from typing import (
    Tuple,
)

from eth import constants

from eth_typing import (
    Address,
)

from eth.exceptions import (
    OutOfGas,
    WriteProtection,
)
from eth.vm.opcode import (
    Opcode,
)

from eth.vm.computation import BaseComputation

from eth._utils.address import (
    force_bytes_to_address,
)


CallParams = Tuple[int, int, Address, Address, Address, int, int, int, int, bool, bool]


class BaseCall(Opcode, ABC):
    @abstractmethod
    def compute_msg_extra_gas(self,
                              computation: BaseComputation,
                              gas: int,
                              to: Address,
                              value: int) -> int:
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def get_call_params(self, computation: BaseComputation) -> CallParams:
        raise NotImplementedError("Must be implemented by subclasses")

    def compute_msg_gas(self,
                        computation: BaseComputation,
                        gas: int,
                        to: Address,
                        value: int) -> Tuple[int, int]:
        extra_gas = self.compute_msg_extra_gas(computation, gas, to, value)
        total_fee = gas + extra_gas
        child_msg_gas = gas + (constants.GAS_CALLSTIPEND if value else 0)
        return child_msg_gas, total_fee

    def __call__(self, computation: BaseComputation) -> None:
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
        ) = self.get_call_params(computation)

        computation.extend_memory(memory_input_start_position, memory_input_size)
        computation.extend_memory(memory_output_start_position, memory_output_size)

        call_data = computation.memory_read(memory_input_start_position, memory_input_size)

        #
        # Message gas allocation and fees
        #
        child_msg_gas, child_msg_gas_fee = self.compute_msg_gas(computation, gas, to, value)
        computation.consume_gas(child_msg_gas_fee, reason=self.mnemonic)

        # Pre-call checks
        sender_balance = computation.state.account_db.get_balance(
            computation.msg.storage_address
        )

        insufficient_funds = should_transfer_value and sender_balance < value
        stack_too_deep = computation.msg.depth + 1 > constants.STACK_DEPTH_LIMIT

        if insufficient_funds or stack_too_deep:
            computation.return_data = b''
            if insufficient_funds:
                err_message = "Insufficient Funds: have: {0} | need: {1}".format(
                    sender_balance,
                    value,
                )
            elif stack_too_deep:
                err_message = "Stack Limit Reached"
            else:
                raise Exception("Invariant: Unreachable code path")

            self.logger.debug2(
                "%s failure: %s",
                self.mnemonic,
                err_message,
            )
            computation.return_gas(child_msg_gas)
            computation.stack_push(0)
        else:
            if code_address:
                code = computation.state.account_db.get_code(code_address)
            else:
                code = computation.state.account_db.get_code(to)

            child_msg_kwargs = {
                'gas': child_msg_gas,
                'value': value,
                'to': to,
                'data': call_data,
                'code': code,
                'code_address': code_address,
                'should_transfer_value': should_transfer_value,
                'is_static': is_static,
            }
            if sender is not None:
                child_msg_kwargs['sender'] = sender

            child_msg = computation.prepare_child_message(**child_msg_kwargs)

            child_computation = computation.apply_child_computation(child_msg)

            if child_computation.is_error:
                computation.stack_push(0)
            else:
                computation.stack_push(1)

            if not child_computation.should_erase_return_data:
                actual_output_size = min(memory_output_size, len(child_computation.output))
                computation.memory_write(
                    memory_output_start_position,
                    actual_output_size,
                    child_computation.output[:actual_output_size],
                )

            if child_computation.should_return_gas:
                computation.return_gas(child_computation.get_gas_remaining())


class Call(BaseCall):
    def compute_msg_extra_gas(self,
                              computation: BaseComputation,
                              gas: int,
                              to: Address,
                              value: int) -> int:
        account_exists = computation.state.account_db.account_exists(to)

        transfer_gas_fee = constants.GAS_CALLVALUE if value else 0
        create_gas_fee = constants.GAS_NEWACCOUNT if not account_exists else 0
        return transfer_gas_fee + create_gas_fee

    def get_call_params(self, computation: BaseComputation) -> CallParams:
        gas = computation.stack_pop(type_hint=constants.UINT256)
        to = force_bytes_to_address(computation.stack_pop(type_hint=constants.BYTES))

        (
            value,
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
        ) = computation.stack_pop(num_items=5, type_hint=constants.UINT256)

        return (
            gas,
            value,
            to,
            None,  # sender
            None,  # code_address
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
            True,  # should_transfer_value,
            computation.msg.is_static,
        )


class CallCode(BaseCall):
    def compute_msg_extra_gas(self,
                              computation: BaseComputation,
                              gas: int,
                              to: Address,
                              value: int) -> int:
        return constants.GAS_CALLVALUE if value else 0

    def get_call_params(self, computation: BaseComputation) -> CallParams:
        gas = computation.stack_pop(type_hint=constants.UINT256)
        code_address = force_bytes_to_address(computation.stack_pop(type_hint=constants.BYTES))

        (
            value,
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
        ) = computation.stack_pop(num_items=5, type_hint=constants.UINT256)

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
        )


class DelegateCall(BaseCall):
    def compute_msg_gas(self,
                        computation: BaseComputation,
                        gas: int,
                        to: Address,
                        value: int) -> Tuple[int, int]:
        return gas, gas

    def compute_msg_extra_gas(self,
                              computation: BaseComputation,
                              gas: int,
                              to: Address,
                              value: int) -> int:
        return 0

    def get_call_params(self, computation: BaseComputation) -> CallParams:
        gas = computation.stack_pop(type_hint=constants.UINT256)
        code_address = force_bytes_to_address(computation.stack_pop(type_hint=constants.BYTES))

        (
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
        ) = computation.stack_pop(num_items=4, type_hint=constants.UINT256)

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
        )


#
# EIP150
#
class CallEIP150(Call):
    def compute_msg_gas(self,
                        computation: BaseComputation,
                        gas: int,
                        to: Address,
                        value: int) -> Tuple[int, int]:
        extra_gas = self.compute_msg_extra_gas(computation, gas, to, value)
        return compute_eip150_msg_gas(
            computation=computation,
            gas=gas,
            extra_gas=extra_gas,
            value=value,
            mnemonic=self.mnemonic,
            callstipend=constants.GAS_CALLSTIPEND
        )


class CallCodeEIP150(CallCode):
    def compute_msg_gas(self,
                        computation: BaseComputation,
                        gas: int,
                        to: Address,
                        value: int) -> Tuple[int, int]:
        extra_gas = self.compute_msg_extra_gas(computation, gas, to, value)
        return compute_eip150_msg_gas(
            computation=computation,
            gas=gas,
            extra_gas=extra_gas,
            value=value,
            mnemonic=self.mnemonic,
            callstipend=constants.GAS_CALLSTIPEND
        )


class DelegateCallEIP150(DelegateCall):
    def compute_msg_gas(self,
                        computation: BaseComputation,
                        gas: int,
                        to: Address,
                        value: int) -> Tuple[int, int]:
        extra_gas = self.compute_msg_extra_gas(computation, gas, to, value)
        callstipend = 0
        return compute_eip150_msg_gas(
            computation=computation,
            gas=gas,
            extra_gas=extra_gas,
            value=value,
            mnemonic=self.mnemonic,
            callstipend=callstipend
        )


def max_child_gas_eip150(gas: int) -> int:
    return gas - (gas // 64)


def compute_eip150_msg_gas(*,
                           computation: BaseComputation,
                           gas: int,
                           extra_gas: int,
                           value: int,
                           mnemonic: str,
                           callstipend: int) -> Tuple[int, int]:
    if computation.get_gas_remaining() < extra_gas:
        # It feels wrong to raise an OutOfGas exception outside of GasMeter,
        # but I don't see an easy way around it.
        raise OutOfGas("Out of gas: Needed {0} - Remaining {1} - Reason: {2}".format(
            extra_gas,
            computation.get_gas_remaining(),
            mnemonic,
        ))
    gas = min(
        gas,
        max_child_gas_eip150(computation.get_gas_remaining() - extra_gas))
    total_fee = gas + extra_gas
    child_msg_gas = gas + (callstipend if value else 0)
    return child_msg_gas, total_fee


#
# EIP161
#
class CallEIP161(CallEIP150):
    def compute_msg_extra_gas(self,
                              computation: BaseComputation,
                              gas: int,
                              to: Address,
                              value: int) -> int:
        account_is_dead = (
            not computation.state.account_db.account_exists(to) or
            computation.state.account_db.account_is_empty(to)
        )

        transfer_gas_fee = constants.GAS_CALLVALUE if value else 0
        create_gas_fee = constants.GAS_NEWACCOUNT if (account_is_dead and value) else 0
        return transfer_gas_fee + create_gas_fee


#
# Byzantium
#
class StaticCall(CallEIP161):
    def get_call_params(self, computation: BaseComputation) -> CallParams:
        gas = computation.stack_pop(type_hint=constants.UINT256)
        to = force_bytes_to_address(computation.stack_pop(type_hint=constants.BYTES))

        (
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
        ) = computation.stack_pop(num_items=4, type_hint=constants.UINT256)

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
        )


class CallByzantium(CallEIP161):
    def get_call_params(self, computation: BaseComputation) -> CallParams:
        call_params = super().get_call_params(computation)
        value = call_params[1]
        if computation.msg.is_static and value != 0:
            raise WriteProtection("Cannot modify state while inside of a STATICCALL context")
        return call_params
