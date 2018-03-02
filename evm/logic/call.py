from evm import constants

from evm.exceptions import (
    OutOfGas,
    WriteProtection,
)
from evm.opcode import (
    Opcode,
)

from evm.utils.address import (
    force_bytes_to_address,
)


class BaseCall(Opcode):
    def compute_msg_extra_gas(self, computation, gas, to, value):
        raise NotImplementedError("Must be implemented by subclasses")

    def get_call_params(self, computation):
        raise NotImplementedError("Must be implemented by subclasses")

    def compute_msg_gas(self, computation, gas, to, value):
        extra_gas = self.compute_msg_extra_gas(computation, gas, to, value)
        total_fee = gas + extra_gas
        child_msg_gas = gas + (constants.GAS_CALLSTIPEND if value else 0)
        return child_msg_gas, total_fee

    def __call__(self, computation):
        computation.gas_meter.consume_gas(
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

        call_data = computation.memory.read(memory_input_start_position, memory_input_size)

        #
        # Message gas allocation and fees
        #
        child_msg_gas, child_msg_gas_fee = self.compute_msg_gas(computation, gas, to, value)
        computation.gas_meter.consume_gas(child_msg_gas_fee, reason=self.mnemonic)

        # Pre-call checks
        with computation.state_db(read_only=True) as state_db:
            sender_balance = state_db.get_balance(computation.msg.storage_address)

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

            self.logger.debug(
                "%s failure: %s",
                self.mnemonic,
                err_message,
            )
            computation.gas_meter.return_gas(child_msg_gas)
            computation.stack.push(0)
        else:
            with computation.state_db(read_only=True) as state_db:
                if code_address:
                    code = state_db.get_code(code_address)
                else:
                    code = state_db.get_code(to)

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
                computation.stack.push(0)
            else:
                computation.stack.push(1)

            if not child_computation.should_erase_return_data:
                actual_output_size = min(memory_output_size, len(child_computation.output))
                computation.memory.write(
                    memory_output_start_position,
                    actual_output_size,
                    child_computation.output[:actual_output_size],
                )

            if child_computation.should_return_gas:
                computation.gas_meter.return_gas(child_computation.gas_meter.gas_remaining)


class Call(BaseCall):
    def compute_msg_extra_gas(self, computation, gas, to, value):
        with computation.state_db(read_only=True) as state_db:
            account_exists = state_db.account_exists(to)

        transfer_gas_fee = constants.GAS_CALLVALUE if value else 0
        create_gas_fee = constants.GAS_NEWACCOUNT if not account_exists else 0
        return transfer_gas_fee + create_gas_fee

    def get_call_params(self, computation):
        gas = computation.stack.pop(type_hint=constants.UINT256)
        to = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))

        (
            value,
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
        ) = computation.stack.pop(num_items=5, type_hint=constants.UINT256)

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
    def compute_msg_extra_gas(self, computation, gas, to, value):
        return constants.GAS_CALLVALUE if value else 0

    def get_call_params(self, computation):
        gas = computation.stack.pop(type_hint=constants.UINT256)
        code_address = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))

        (
            value,
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
        ) = computation.stack.pop(num_items=5, type_hint=constants.UINT256)

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
    def compute_msg_gas(self, computation, gas, to, value):
        return gas, gas

    def compute_msg_extra_gas(self, computation, gas, to, value):
        return 0

    def get_call_params(self, computation):
        gas = computation.stack.pop(type_hint=constants.UINT256)
        code_address = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))

        (
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
        ) = computation.stack.pop(num_items=4, type_hint=constants.UINT256)

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
    def compute_msg_gas(self, computation, gas, to, value):
        extra_gas = self.compute_msg_extra_gas(computation, gas, to, value)
        return compute_eip150_msg_gas(
            computation, gas, extra_gas, value, self.mnemonic,
            constants.GAS_CALLSTIPEND)


class CallCodeEIP150(CallCode):
    def compute_msg_gas(self, computation, gas, to, value):
        extra_gas = self.compute_msg_extra_gas(computation, gas, to, value)
        return compute_eip150_msg_gas(
            computation, gas, extra_gas, value, self.mnemonic,
            constants.GAS_CALLSTIPEND)


class DelegateCallEIP150(DelegateCall):
    def compute_msg_gas(self, computation, gas, to, value):
        extra_gas = self.compute_msg_extra_gas(computation, gas, to, value)
        callstipend = 0
        return compute_eip150_msg_gas(
            computation, gas, extra_gas, value, self.mnemonic, callstipend)


def max_child_gas_eip150(gas):
    return gas - (gas // 64)


def compute_eip150_msg_gas(computation, gas, extra_gas, value, mnemonic, callstipend):
    if computation.gas_meter.gas_remaining < extra_gas:
        # It feels wrong to raise an OutOfGas exception outside of GasMeter,
        # but I don't see an easy way around it.
        raise OutOfGas("Out of gas: Needed {0} - Remaining {1} - Reason: {2}".format(
            extra_gas,
            computation.gas_meter.gas_remaining,
            mnemonic,
        ))
    gas = min(
        gas,
        max_child_gas_eip150(computation.gas_meter.gas_remaining - extra_gas))
    total_fee = gas + extra_gas
    child_msg_gas = gas + (callstipend if value else 0)
    return child_msg_gas, total_fee


#
# EIP161
#
class CallEIP161(CallEIP150):
    def compute_msg_extra_gas(self, computation, gas, to, value):
        with computation.state_db(read_only=True) as state_db:
            account_is_dead = (
                not state_db.account_exists(to) or
                state_db.account_is_empty(to)
            )

        transfer_gas_fee = constants.GAS_CALLVALUE if value else 0
        create_gas_fee = constants.GAS_NEWACCOUNT if (account_is_dead and value) else 0
        return transfer_gas_fee + create_gas_fee


#
# Byzantium
#
class StaticCall(CallEIP161):
    def get_call_params(self, computation):
        gas = computation.stack.pop(type_hint=constants.UINT256)
        to = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))

        (
            memory_input_start_position,
            memory_input_size,
            memory_output_start_position,
            memory_output_size,
        ) = computation.stack.pop(num_items=4, type_hint=constants.UINT256)

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
    def get_call_params(self, computation):
        call_params = super(CallByzantium, self).get_call_params(computation)
        value = call_params[1]
        if computation.msg.is_static and value != 0:
            raise WriteProtection("Cannot modify state while inside of a STATICCALL context")
        return call_params


class CallSharding(CallByzantium):
    def compute_msg_extra_gas(self, computation, gas, to, value):
        with computation.state_db(read_only=True) as state_db:
            account_is_empty = state_db.account_is_empty(to)

        transfer_gas_fee = constants.GAS_CALLVALUE if value else 0
        create_gas_fee = constants.GAS_NEWACCOUNT if account_is_empty else 0
        return transfer_gas_fee + create_gas_fee

    def __call__(self, computation):
        computation.gas_meter.consume_gas(
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

        call_data = computation.memory.read(memory_input_start_position, memory_input_size)

        #
        # Message gas allocation and fees
        #
        child_msg_gas, child_msg_gas_fee = self.compute_msg_gas(computation, gas, to, value)
        computation.gas_meter.consume_gas(child_msg_gas_fee, reason=self.mnemonic)

        # Pre-call checks
        with computation.state_db(read_only=True) as state_db:
            sender_balance = state_db.get_balance(computation.msg.storage_address)

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

            self.logger.debug(
                "%s failure: %s",
                self.mnemonic,
                err_message,
            )
            computation.gas_meter.return_gas(child_msg_gas)
            computation.stack.push(0)
        else:
            with computation.state_db(read_only=True) as state_db:
                if code_address:
                    code = state_db.get_code(code_address)
                else:
                    code = state_db.get_code(to)

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
                computation.stack.push(0)
            else:
                computation.stack.push(1)

            if not child_computation.should_erase_return_data:
                actual_output_size = min(memory_output_size, len(child_computation.output))
                computation.memory.write(
                    memory_output_start_position,
                    actual_output_size,
                    child_computation.output[:actual_output_size],
                )

            if not child_computation.should_burn_gas:
                computation.gas_meter.return_gas(child_computation.gas_meter.gas_remaining)
