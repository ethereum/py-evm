from evm import constants
from evm import mnemonics
from evm.exceptions import (
    Halt,
    Revert,
    WriteProtection,
    InsufficientFunds,
    GasPriceAlreadySet,
    NotTopLevelCall
)

from evm.opcode import (
    Opcode,
)
from evm.utils.address import (
    force_bytes_to_address,
    generate_contract_address,
    generate_CREATE2_contract_address,
)
from evm.utils.hexadecimal import (
    encode_hex,
)

from .call import max_child_gas_eip150


def return_op(computation):
    start_position, size = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    computation.extend_memory(start_position, size)

    output = computation.memory.read(start_position, size)
    computation.output = bytes(output)
    raise Halt('RETURN')


def revert(computation):
    start_position, size = computation.stack.pop(num_items=2, type_hint=constants.UINT256)

    computation.extend_memory(start_position, size)

    output = computation.memory.read(start_position, size)
    computation.output = bytes(output)
    raise Revert(computation.output)


def selfdestruct(computation):
    beneficiary = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))
    _selfdestruct(computation, beneficiary)
    raise Halt('SELFDESTRUCT')


def selfdestruct_eip150(computation):
    beneficiary = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))
    with computation.state_db(read_only=True) as state_db:
        if not state_db.account_exists(beneficiary):
            computation.gas_meter.consume_gas(
                constants.GAS_SELFDESTRUCT_NEWACCOUNT,
                reason=mnemonics.SELFDESTRUCT,
            )
    _selfdestruct(computation, beneficiary)


def selfdestruct_eip161(computation):
    beneficiary = force_bytes_to_address(computation.stack.pop(type_hint=constants.BYTES))
    with computation.state_db(read_only=True) as state_db:
        is_dead = (
            not state_db.account_exists(beneficiary) or
            state_db.account_is_empty(beneficiary)
        )
        if is_dead and state_db.get_balance(computation.msg.storage_address):
            computation.gas_meter.consume_gas(
                constants.GAS_SELFDESTRUCT_NEWACCOUNT,
                reason=mnemonics.SELFDESTRUCT,
            )
    _selfdestruct(computation, beneficiary)


def _selfdestruct(computation, beneficiary):
    with computation.state_db() as state_db:
        local_balance = state_db.get_balance(computation.msg.storage_address)
        beneficiary_balance = state_db.get_balance(beneficiary)

        # 1st: Transfer to beneficiary
        state_db.set_balance(beneficiary, local_balance + beneficiary_balance)
        # 2nd: Zero the balance of the address being deleted (must come after
        # sending to beneficiary in case the contract named itself as the
        # beneficiary.
        state_db.set_balance(computation.msg.storage_address, 0)

    computation.vm_state.logger.debug(
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
        computation.gas_meter.consume_gas(self.gas_cost, reason=self.mnemonic)

        value, start_position, size = computation.stack.pop(
            num_items=3,
            type_hint=constants.UINT256,
        )

        computation.extend_memory(start_position, size)

        with computation.state_db(read_only=True) as state_db:
            insufficient_funds = state_db.get_balance(computation.msg.storage_address) < value
        stack_too_deep = computation.msg.depth + 1 > constants.STACK_DEPTH_LIMIT

        if insufficient_funds or stack_too_deep:
            computation.stack.push(0)
            return

        call_data = computation.memory.read(start_position, size)

        create_msg_gas = self.max_child_gas_modifier(
            computation.gas_meter.gas_remaining
        )
        computation.gas_meter.consume_gas(create_msg_gas, reason="CREATE")

        with computation.state_db() as state_db:
            creation_nonce = state_db.get_nonce(computation.msg.storage_address)
            state_db.increment_nonce(computation.msg.storage_address)

            contract_address = generate_contract_address(
                computation.msg.storage_address,
                creation_nonce,
            )

            is_collision = state_db.account_has_code_or_nonce(contract_address)

        if is_collision:
            computation.vm_state.logger.debug(
                "Address collision while creating contract: %s",
                encode_hex(contract_address),
            )
            computation.stack.push(0)
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
            computation.stack.push(0)
        else:
            computation.stack.push(contract_address)
        computation.gas_meter.return_gas(child_computation.gas_meter.gas_remaining)


class CreateEIP150(Create):
    def max_child_gas_modifier(self, gas):
        return max_child_gas_eip150(gas)


class CreateByzantium(CreateEIP150):
    def __call__(self, computation):
        if computation.msg.is_static:
            raise WriteProtection("Cannot modify state while inside of a STATICCALL context")
        return super(CreateEIP150, self).__call__(computation)


class Create2(CreateEIP150):
    def __call__(self, computation):
        if computation.msg.is_static:
            raise WriteProtection("Cannot modify state while inside of a STATICCALL context")

        computation.gas_meter.consume_gas(self.gas_cost, reason=self.mnemonic)

        value = computation.stack.pop(type_hint=constants.UINT256,)
        salt = computation.stack.pop(type_hint=constants.BYTES,)
        start_position, size = computation.stack.pop(
            num_items=2,
            type_hint=constants.UINT256,
        )

        computation.extend_memory(start_position, size)

        with computation.state_db(read_only=True) as state_db:
            insufficient_funds = state_db.get_balance(computation.msg.storage_address) < value
        stack_too_deep = computation.msg.depth + 1 > constants.STACK_DEPTH_LIMIT

        if insufficient_funds or stack_too_deep:
            computation.stack.push(0)
            return

        call_data = computation.memory.read(start_position, size)

        create_msg_gas = self.max_child_gas_modifier(
            computation.gas_meter.gas_remaining
        )
        computation.gas_meter.consume_gas(create_msg_gas, reason="CREATE2")

        contract_address = generate_CREATE2_contract_address(
            salt,
            call_data,
        )

        with computation.state_db(read_only=True) as state_db:
            is_collision = state_db.account_has_code(contract_address)

        if is_collision:
            computation.vm.logger.debug(
                "Address collision while creating contract: %s",
                encode_hex(contract_address),
            )
            computation.stack.push(0)
            return

        child_msg = computation.prepare_child_message(
            gas=create_msg_gas,
            to=contract_address,
            value=value,
            data=b'',
            code=call_data,
            is_create=True,
        )

        child_computation = computation.apply_child_computation(child_msg)

        if child_computation.is_error:
            computation.stack.push(0)
        else:
            computation.stack.push(contract_address)
        computation.gas_meter.return_gas(child_computation.gas_meter.gas_remaining)


def paygas(computation):
    gas_price = computation.stack.pop(type_hint=constants.UINT256)

    # Only valid if (1) triggered in a top level call and
    # (2) not been set already during this transaction execution
    try:
        computation.set_PAYGAS_gasprice(gas_price)
    except (GasPriceAlreadySet, NotTopLevelCall):
        computation.stack.push(0)
    else:
        with computation.state_db(read_only=False) as state_db:
            tx_initiator = computation.msg.to
            tx_initiator_balance = state_db.get_balance(tx_initiator)

            PAYGAS_gasprice = computation.get_PAYGAS_gas_price()
            if PAYGAS_gasprice is None:
                PAYGAS_gasprice = 0
            fee_to_be_charged = (
                PAYGAS_gasprice * computation.transaction_context.transaction_gas_limit
            )

            if tx_initiator_balance < fee_to_be_charged:
                raise InsufficientFunds(
                    "Insufficient funds: {0} < {1}".format(
                        tx_initiator_balance,
                        fee_to_be_charged
                    )
                )

            state_db.delta_balance(tx_initiator, -1 * fee_to_be_charged)
        computation.stack.push(1)
