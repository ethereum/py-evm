from eth_typing import (
    Address,
)

from eth import constants
from eth.exceptions import (
    Halt,
    Revert,
    WriteProtection,
)

from eth.utils.address import (
    force_bytes_to_address,
    generate_contract_address,
    generate_safe_contract_address,
)
from eth.utils.hexadecimal import (
    encode_hex,
)
from eth.vm import mnemonics
from eth.vm.computation import (
    BaseComputation
)
from eth.vm.opcode import (
    Opcode,
)

from .call import max_child_gas_eip150


def return_op(computation: BaseComputation) -> None:
    start_position, size = computation.stack_pop(num_items=2, type_hint=constants.UINT256)

    computation.extend_memory(start_position, size)

    output = computation.memory_read(start_position, size)
    computation.output = bytes(output)
    raise Halt('RETURN')


def revert(computation: BaseComputation) -> None:
    start_position, size = computation.stack_pop(num_items=2, type_hint=constants.UINT256)

    computation.extend_memory(start_position, size)

    output = computation.memory_read(start_position, size)
    computation.output = bytes(output)
    raise Revert(computation.output)


def selfdestruct(computation: BaseComputation) -> None:
    beneficiary = force_bytes_to_address(computation.stack_pop(type_hint=constants.BYTES))
    _selfdestruct(computation, beneficiary)
    raise Halt('SELFDESTRUCT')


def selfdestruct_eip150(computation: BaseComputation) -> None:
    beneficiary = force_bytes_to_address(computation.stack_pop(type_hint=constants.BYTES))
    if not computation.state.account_db.account_exists(beneficiary):
        computation.consume_gas(
            constants.GAS_SELFDESTRUCT_NEWACCOUNT,
            reason=mnemonics.SELFDESTRUCT,
        )
    _selfdestruct(computation, beneficiary)


def selfdestruct_eip161(computation: BaseComputation) -> None:
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


def _selfdestruct(computation: BaseComputation, beneficiary: Address) -> None:
    local_balance = computation.state.account_db.get_balance(computation.msg.storage_address)
    beneficiary_balance = computation.state.account_db.get_balance(beneficiary)

    # 1st: Transfer to beneficiary
    computation.state.account_db.set_balance(beneficiary, local_balance + beneficiary_balance)
    # 2nd: Zero the balance of the address being deleted (must come after
    # sending to beneficiary in case the contract named itself as the
    # beneficiary.
    computation.state.account_db.set_balance(computation.msg.storage_address, 0)

    computation.logger.trace(
        "SELFDESTRUCT: %s (%s) -> %s",
        encode_hex(computation.msg.storage_address),
        local_balance,
        encode_hex(beneficiary),
    )

    # 3rd: Register the account to be deleted
    computation.register_account_for_deletion(beneficiary)
    raise Halt('SELFDESTRUCT')


class CreateOpcodeStackData:

    def __init__(self,
                 endowment: int,
                 memory_start: int,
                 memory_length: int,
                 salt: int = None) -> None:

        self.endowment = endowment
        self.memory_start = memory_start
        self.memory_length = memory_length
        self.salt = salt


class Create(Opcode):

    def max_child_gas_modifier(self, gas: int) -> int:
        return gas

    def generate_contract_address(self,
                                  stack_data: CreateOpcodeStackData,
                                  call_data: bytes,
                                  computation: BaseComputation) -> Address:

        creation_nonce = computation.state.account_db.get_nonce(computation.msg.storage_address)
        computation.state.account_db.increment_nonce(computation.msg.storage_address)

        contract_address = generate_contract_address(
            computation.msg.storage_address,
            creation_nonce,
        )

        return contract_address

    def get_stack_data(self, computation: BaseComputation) -> CreateOpcodeStackData:
        endowment, memory_start, memory_length = computation.stack_pop(
            num_items=3,
            type_hint=constants.UINT256,
        )

        return CreateOpcodeStackData(endowment, memory_start, memory_length)

    def __call__(self, computation: BaseComputation) -> None:
        computation.consume_gas(self.gas_cost, reason=self.mnemonic)

        stack_data = self.get_stack_data(computation)

        computation.extend_memory(stack_data.memory_start, stack_data.memory_length)

        insufficient_funds = computation.state.account_db.get_balance(
            computation.msg.storage_address
        ) < stack_data.endowment
        stack_too_deep = computation.msg.depth + 1 > constants.STACK_DEPTH_LIMIT

        if insufficient_funds or stack_too_deep:
            computation.stack_push(0)
            return

        call_data = computation.memory_read(stack_data.memory_start, stack_data.memory_length)

        create_msg_gas = self.max_child_gas_modifier(
            computation.get_gas_remaining()
        )
        computation.consume_gas(create_msg_gas, reason=self.mnemonic)

        contract_address = self.generate_contract_address(stack_data, call_data, computation)

        is_collision = computation.state.account_db.account_has_code_or_nonce(contract_address)

        if is_collision:
            self.logger.trace(
                "Address collision while creating contract: %s",
                encode_hex(contract_address),
            )
            computation.stack_push(0)
            return

        child_msg = computation.prepare_child_message(
            gas=create_msg_gas,
            to=constants.CREATE_CONTRACT_ADDRESS,
            value=stack_data.endowment,
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
    def max_child_gas_modifier(self, gas: int) -> int:
        return max_child_gas_eip150(gas)


class CreateByzantium(CreateEIP150):
    def __call__(self, computation: BaseComputation) -> None:
        if computation.msg.is_static:
            raise WriteProtection("Cannot modify state while inside of a STATICCALL context")
        return super().__call__(computation)


class Create2(CreateByzantium):

    def get_stack_data(self, computation: BaseComputation) -> CreateOpcodeStackData:

        endowment, memory_start, memory_length, salt = computation.stack_pop(
            num_items=4,
            type_hint=constants.UINT256,
        )

        return CreateOpcodeStackData(endowment, memory_start, memory_length, salt)

    def generate_contract_address(self,
                                  stack_data: CreateOpcodeStackData,
                                  call_data: bytes,
                                  computation: BaseComputation) -> Address:

        return generate_safe_contract_address(
            computation.msg.storage_address,
            stack_data.salt,
            call_data
        )
