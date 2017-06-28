from __future__ import absolute_import


from evm import VM
from evm import constants

from evm import opcode_values
from evm.exceptions import (
    OutOfGas,
    InsufficientFunds,
    StackDepthLimit,
)
from evm.precompile import (
    PRECOMPILES,
)

from evm.vm.message import (
    Message,
)
from evm.vm.computation import (
    Computation,
)

from evm.utils.address import (
    generate_contract_address,
)
from evm.utils.hexidecimal import (
    encode_hex,
)

from .opcodes import FRONTIER_OPCODES
from .blocks import FrontierBlock
from .validation import validate_frontier_transaction
from .headers import (
    create_frontier_header_from_parent,
    configure_frontier_header,
)


BREAK_OPCODES = {
    opcode_values.RETURN,
    opcode_values.STOP,
    opcode_values.SUICIDE,
}


def _execute_frontier_transaction(vm, transaction):
    #
    # 1) Pre Computation
    #

    # Validate the transaction
    transaction.validate()

    vm.validate_transaction(transaction)

    gas_cost = transaction.gas * transaction.gas_price
    sender_balance = vm.state_db.get_balance(transaction.sender)

    # Buy Gas
    vm.state_db.set_balance(transaction.sender, sender_balance - gas_cost)

    # Increment Nonce
    vm.state_db.increment_nonce(transaction.sender)

    # Setup VM Message
    message_gas = transaction.gas - transaction.intrensic_gas

    if transaction.to == constants.CREATE_CONTRACT_ADDRESS:
        contract_address = generate_contract_address(
            transaction.sender,
            vm.state_db.get_nonce(transaction.sender) - 1,
        )
        data = b''
        code = transaction.data
    else:
        contract_address = None
        data = transaction.data
        code = vm.state_db.get_code(transaction.to)

    if vm.logger:
        vm.logger.info(
            (
                "TRANSACTION: sender: %s | to: %s | value: %s | gas: %s | "
                "gas-price: %s | s: %s | r: %s | v: %s | data: %s"
            ),
            encode_hex(transaction.sender),
            encode_hex(transaction.to),
            transaction.value,
            transaction.gas,
            transaction.gas_price,
            transaction.s,
            transaction.r,
            transaction.v,
            encode_hex(transaction.data),
        )

    message = Message(
        gas=message_gas,
        gas_price=transaction.gas_price,
        to=transaction.to,
        sender=transaction.sender,
        value=transaction.value,
        data=data,
        code=code,
        create_address=contract_address,
    )

    #
    # 2) Apply the message to the VM.
    #
    if message.is_create:
        computation = vm.apply_create_message(message)
    else:
        computation = vm.apply_message(message)

    #
    # 2) Post Computation
    #
    if computation.error:
        # Miner Fees
        transaction_fee = transaction.gas * transaction.gas_price
        if vm.logger:
            vm.logger.debug('TRANSACTION FEE: %s', transaction_fee)
        coinbase_balance = vm.state_db.get_balance(vm.block.header.coinbase)
        vm.state_db.set_balance(
            vm.block.header.coinbase,
            coinbase_balance + transaction_fee,
        )
    else:
        # Suicide Refunds
        num_deletions = len(computation.get_accounts_for_deletion())
        if num_deletions:
            computation.gas_meter.refund_gas(constants.REFUND_SUICIDE * num_deletions)

        # Gas Refunds
        gas_remaining = computation.get_gas_remaining()
        gas_refunded = computation.get_gas_refund()
        gas_used = transaction.gas - gas_remaining
        gas_refund = min(gas_refunded, gas_used // 2)
        gas_refund_amount = (gas_refund + gas_remaining) * transaction.gas_price

        if gas_refund_amount:
            if vm.logger:
                vm.logger.debug(
                    'TRANSACTION REFUND: %s -> %s',
                    gas_refund_amount,
                    encode_hex(message.sender),
                )

            sender_balance = vm.state_db.get_balance(message.sender)
            vm.state_db.set_balance(message.sender, sender_balance + gas_refund_amount)

        # Miner Fees
        transaction_fee = (transaction.gas - gas_remaining - gas_refund) * transaction.gas_price
        if vm.logger:
            vm.logger.debug(
                'TRANSACTION FEE: %s -> %s',
                transaction_fee,
                encode_hex(vm.block.header.coinbase),
            )
        coinbase_balance = vm.state_db.get_balance(vm.block.header.coinbase)
        vm.state_db.set_balance(
            vm.block.header.coinbase,
            coinbase_balance + transaction_fee,
        )

    # Suicides
    for account, beneficiary in computation.get_accounts_for_deletion():
        # TODO: need to figure out how we prevent multiple suicides from
        # the same account and if this is the right place to put this.
        if vm.logger is not None:
            vm.logger.debug('DELETING ACCOUNT: %s', encode_hex(account))

        vm.state_db.set_balance(account, 0)
        vm.state_db.delete_account(account)

    vm.block.header.state_root = vm.state_db.root_hash

    return computation


def _apply_frontier_message(vm, message):
    snapshot = vm.snapshot()

    if message.depth > constants.STACK_DEPTH_LIMIT:
        raise StackDepthLimit("Stack depth limit reached")

    if message.should_transfer_value and message.value:
        sender_balance = vm.state_db.get_balance(message.sender)

        if sender_balance < message.value:
            raise InsufficientFunds(
                "Insufficient funds: {0} < {1}".format(sender_balance, message.value)
            )

        sender_balance -= message.value
        vm.state_db.set_balance(message.sender, sender_balance)

        recipient_balance = vm.state_db.get_balance(message.storage_address)
        recipient_balance += message.value
        vm.state_db.set_balance(message.storage_address, recipient_balance)

        if vm.logger is not None:
            vm.logger.debug(
                "TRANSFERRED: %s from %s -> %s",
                message.value,
                encode_hex(message.sender),
                encode_hex(message.storage_address),
            )

    if not vm.state_db.account_exists(message.storage_address):
        vm.state_db.touch_account(message.storage_address)

    computation = vm.apply_computation(message)

    if computation.error:
        vm.revert(snapshot)
    return computation


def _apply_frontier_computation(vm, message):
    computation = Computation(vm, message)

    with computation:
        # Early exit on pre-compiles
        if computation.msg.code_address in PRECOMPILES:
            return PRECOMPILES[computation.msg.code_address](computation)

        for opcode in computation.code:
            opcode_fn = computation.vm.get_opcode_fn(opcode)

            if computation.logger is not None:
                computation.logger.trace(
                    "OPCODE: 0x%x (%s)",
                    opcode,
                    opcode_fn.mnemonic,
                )

            opcode_fn(computation=computation)

            if opcode in BREAK_OPCODES:
                break

    return computation


def _apply_frontier_create_message(vm, message):
    if vm.state_db.get_balance(message.storage_address) > 0:
        vm.state_db.set_nonce(message.storage_address, 0)
        vm.state_db.set_code(message.storage_address, b'')
        # TODO: figure out whether the following line is correct.
        vm.state_db.delete_storage(message.storage_address)

    if message.sender != message.origin:
        vm.state_db.increment_nonce(message.sender)

    computation = vm.apply_message(message)

    if computation.error:
        return computation
    else:
        contract_code = computation.output

        if contract_code:
            contract_code_gas_cost = len(contract_code) * constants.GAS_CODEDEPOSIT
            try:
                computation.gas_meter.consume_gas(
                    contract_code_gas_cost,
                    reason="Write contract code for CREATE",
                )
            except OutOfGas as err:
                computation.output = b''
            else:
                if vm.logger:
                    vm.logger.debug(
                        "SETTING CODE: %s -> %s",
                        encode_hex(message.storage_address),
                        contract_code,
                    )
                computation.state_db.set_code(message.storage_address, contract_code)
        return computation


FrontierVM = VM.configure(
    name='FrontierVM',
    # VM logic
    opcodes=FRONTIER_OPCODES,
    # classes
    _block_class=FrontierBlock,
    # helpers
    create_header_from_parent=staticmethod(create_frontier_header_from_parent),
    configure_header=configure_frontier_header,
    # validation
    validate_transaction=validate_frontier_transaction,
    # transactions and vm messages
    execute_transaction=_execute_frontier_transaction,
    apply_create_message=_apply_frontier_create_message,
    apply_message=_apply_frontier_message,
    apply_computation=_apply_frontier_computation,
)
