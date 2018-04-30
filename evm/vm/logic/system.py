from evm import constants
from evm.exceptions import (
    Halt,
    Revert,
    WriteProtection,
)

from evm.utils.address import (
    force_bytes_to_address,
    generate_contract_address,
)
from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.vm import mnemonics
from evm.vm.opcode import (
    Opcode,
)

from .call import max_child_gas_eip150


def return_op(computation):
    start_position, size = computation.stack_pop(num_items=2, type_hint=constants.UINT256)

    computation.extend_memory(start_position, size)

    output = computation.memory_read(start_position, size)
    computation.output = bytes(output)
    raise Halt('RETURN')


def revert(computation):
    start_position, size = computation.stack_pop(num_items=2, type_hint=constants.UINT256)

    computation.extend_memory(start_position, size)

    output = computation.memory_read(start_position, size)
    computation.output = bytes(output)
    raise Revert(computation.output)


def selfdestruct(computation):
    beneficiary = force_bytes_to_address(computation.stack_pop(type_hint=constants.BYTES))
    _selfdestruct(computation, beneficiary)
    raise Halt('SELFDESTRUCT')


def selfdestruct_eip150(computation):
    beneficiary = force_bytes_to_address(computation.stack_pop(type_hint=constants.BYTES))
    if not computation.state.account_db.account_exists(beneficiary):
        computation.consume_gas(
            constants.GAS_SELFDESTRUCT_NEWACCOUNT,
            reason=mnemonics.SELFDESTRUCT,
        )
    _selfdestruct(computation, beneficiary)


def selfdestruct_eip161(computation):
    beneficiary = force_bytes_to_address(computation.stack_pop(type_hint=constants.BYTES))
    is_dead = (
        not computation.state.account_db.account_exists(beneficiary) or
        computation.state.account_db.account_is_empty(beneficiary)
    )
    if is_dead and computation.state.account_db.get_balance(computation.msg.storage_address):
        computation.consume_gas(
            constants.GAS_SELFDESTRUCT_NEWACCOUNT,
            reason=mnemonics.SELFDESTRUCT,
        )
    _selfdestruct(computation, beneficiary)


def _selfdestruct(computation, beneficiary):
    local_balance = computation.state.account_db.get_balance(computation.msg.storage_address)
    beneficiary_balance = computation.state.account_db.get_balance(beneficiary)

    # 1st: Transfer to beneficiary
    computation.state.account_db.set_balance(beneficiary, local_balance + beneficiary_balance)
    # 2nd: Zero the balance of the address being deleted (must come after
    # sending to beneficiary in case the contract named itself as the
    # beneficiary.
    computation.state.account_db.set_balance(computation.msg.storage_address, 0)

    computation.logger.debug(
        "SELFDESTRUCT: %s (%s) -> %s",
        encode_hex(computation.msg.storage_address),
        local_balance,
        encode_hex(beneficiary),
    )

    # 3rd: Register the account to be deleted
    computation.register_account_for_deletion(beneficiary)
    raise Halt('SELFDESTRUCT')


class Create(Opcode):
    def max_child_gas_modifier(self, gas):
        return gas

    def __call__(self, computation):
        computation.consume_gas(self.gas_cost, reason=self.mnemonic)

        value, start_position, size = computation.stack_pop(
            num_items=3,
            type_hint=constants.UINT256,
        )

        computation.extend_memory(start_position, size)

        insufficient_funds = computation.state.account_db.get_balance(
            computation.msg.storage_address
        ) < value
        stack_too_deep = computation.msg.depth + 1 > constants.STACK_DEPTH_LIMIT

        if insufficient_funds or stack_too_deep:
            computation.stack_push(0)
            return

        call_data = computation.memory_read(start_position, size)

        create_msg_gas = self.max_child_gas_modifier(
            computation.get_gas_remaining()
        )
        computation.consume_gas(create_msg_gas, reason="CREATE")

        creation_nonce = computation.state.account_db.get_nonce(computation.msg.storage_address)
        computation.state.account_db.increment_nonce(computation.msg.storage_address)

        contract_address = generate_contract_address(
            computation.msg.storage_address,
            creation_nonce,
        )

        is_collision = computation.state.account_db.account_has_code_or_nonce(contract_address)

        if is_collision:
            self.logger.debug(
                "Address collision while creating contract: %s",
                encode_hex(contract_address),
            )
            computation.stack_push(0)
            return

        child_msg = computation.prepare_child_message(
            gas=create_msg_gas,
            to=constants.CREATE_CONTRACT_ADDRESS,
            value=value,
            data=b'',
            code=call_data,
            create_address=contract_address,
        )

        child_computation = computation.apply_child_computation(child_msg)

        if child_computation.is_error:
            computation.stack_push(0)
        else:
            computation.stack_push(contract_address)
        computation.return_gas(child_computation.get_gas_remaining())


class CreateEIP150(Create):
    def max_child_gas_modifier(self, gas):
        return max_child_gas_eip150(gas)


class CreateByzantium(CreateEIP150):
    def __call__(self, computation):
        if computation.msg.is_static:
            raise WriteProtection("Cannot modify state while inside of a STATICCALL context")
        return super(CreateEIP150, self).__call__(computation)
