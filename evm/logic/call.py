from evm import constants

from evm.opcode import (
    Opcode,
)

from evm.utils.address import (
    force_bytes_to_address,
)


class BaseCall(Opcode):
    def compute_msg_gas(self, computation, gas, to, value):
        raise NotImplementedError("Must be implemented by subclasses")

    def get_call_params(self, computation):
        raise NotImplementedError("Must be implemented by subclasses")

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
        sender_balance = computation.state_db.get_balance(
            computation.msg.storage_address,
        )
        insufficient_funds = should_transfer_value and sender_balance < value
        stack_too_deep = computation.msg.depth + 1 > constants.STACK_DEPTH_LIMIT

        if insufficient_funds or stack_too_deep:
            if self.logger:
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
            if code_address:
                code = computation.state_db.get_code(code_address)
            else:
                code = computation.state_db.get_code(to)

            child_msg_kwargs = {
                'gas': child_msg_gas,
                'value': value,
                'to': to,
                'data': call_data,
                'code': code,
                'code_address': code_address,
                'should_transfer_value': should_transfer_value,
            }
            if sender is not None:
                child_msg_kwargs['sender'] = sender

            child_msg = computation.prepare_child_message(**child_msg_kwargs)

            if child_msg.is_create:
                child_computation = computation.vm.apply_create_message(child_msg)
            else:
                child_computation = computation.vm.apply_message(child_msg)

            computation.children.append(child_computation)

            if child_computation.error:
                computation.stack.push(0)
            else:
                actual_output_size = min(memory_output_size, len(child_computation.output))
                computation.gas_meter.return_gas(child_computation.gas_meter.gas_remaining)
                computation.memory.write(
                    memory_output_start_position,
                    actual_output_size,
                    child_computation.output[:actual_output_size],
                )
                computation.stack.push(1)


class Call(BaseCall):
    def compute_msg_gas(self, computation, gas, to, value):
        account_exists = computation.state_db.account_exists(to)
        transfer_gas_fee = constants.GAS_CALLVALUE if value else 0
        create_gas_fee = constants.GAS_NEWACCOUNT if not account_exists else 0

        total_fee = gas + transfer_gas_fee + create_gas_fee

        child_msg_gas = gas + (constants.GAS_CALLSTIPEND if value else 0)
        return child_msg_gas, total_fee

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
        )


class CallCode(BaseCall):
    def compute_msg_gas(self, computation, gas, to, value):
        transfer_gas_cost = constants.GAS_CALLVALUE if value else 0

        total_fee = transfer_gas_cost + gas
        child_msg_gas = gas + (constants.GAS_CALLSTIPEND if value else 0)
        return child_msg_gas, total_fee

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
        )


class DelegateCall(CallCode):
    def compute_msg_gas(self, computation, gas, to, value):
        return gas, gas

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
        )
