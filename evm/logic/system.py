from evm import constants
from evm import mnemonics

from evm.opcode import (
    Opcode,
)
from evm.utils.address import (
    force_bytes_to_address,
    generate_contract_address,
)

from .call import max_child_gas_eip150


def return_op(computation):
    start_position, size = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    computation.extend_memory(start_position, size)

    output = computation.memory.read(start_position, size)
    computation.output = bytes(output)


def suicide(computation):
    beneficiary = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))
    _suicide(computation, beneficiary)


def suicide_eip150(computation):
    beneficiary = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))
    if not computation.state_db.account_exists(beneficiary):
        computation.gas_meter.consume_gas(
            constants.GAS_SUICIDE_NEWACCOUNT, reason=mnemonics.SUICIDE)
    _suicide(computation, beneficiary)


def _suicide(computation, beneficiary):
    local_balance = computation.state_db.get_balance(computation.msg.storage_address)
    beneficiary_balance = computation.state_db.get_balance(beneficiary)

    # 1st: Transfer to beneficiary
    computation.state_db.set_balance(
        beneficiary,
        local_balance + beneficiary_balance,
    )
    # 2nd: Zero the balance of the address being deleted (must come after
    # sending to beneficiary in case the contract named itself as the
    # beneficiary.
    computation.state_db.set_balance(computation.msg.storage_address, 0)

    # 3rd: Register the account to be deleted
    computation.register_account_for_deletion(computation.msg.storage_address)


class Create(Opcode):
    def max_child_gas_modifier(self, gas):
        return gas

    def __call__(self, computation):
        computation.gas_meter.consume_gas(self.gas_cost, reason=self.mnemonic)

        value, start_position, size = computation.stack.pop(
            num_items=3,
            type_hint=constants.UINT256,
        )

        computation.extend_memory(start_position, size)

        insufficient_funds = computation.state_db.get_balance(
            computation.msg.storage_address) < value
        stack_too_deep = computation.msg.depth + 1 > constants.STACK_DEPTH_LIMIT

        if insufficient_funds or stack_too_deep:
            computation.stack.push(0)
            return

        call_data = computation.memory.read(start_position, size)

        create_msg_gas = self.max_child_gas_modifier(
            computation.gas_meter.gas_remaining)
        computation.gas_meter.consume_gas(create_msg_gas, reason="CREATE")

        creation_nonce = computation.state_db.get_nonce(
            computation.msg.storage_address)
        contract_address = generate_contract_address(
            computation.msg.storage_address, creation_nonce)

        child_msg = computation.prepare_child_message(
            gas=create_msg_gas,
            to=constants.CREATE_CONTRACT_ADDRESS,
            value=value,
            data=b'',
            code=call_data,
            create_address=contract_address,
        )

        if child_msg.is_create:
            child_computation = computation.vm.apply_create_message(child_msg)
        else:
            child_computation = computation.vm.apply_message(child_msg)

        computation.children.append(child_computation)

        if child_computation.error:
            computation.stack.push(0)
        else:
            computation.gas_meter.return_gas(child_computation.gas_meter.gas_remaining)
            computation.stack.push(contract_address)


class CreateEIP150(Create):
    def max_child_gas_modifier(self, gas):
        return max_child_gas_eip150(gas)
