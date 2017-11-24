from __future__ import absolute_import


from evm import VM
from evm import constants

from evm.exceptions import (
    OutOfGas,
    InsufficientFunds,
    StackDepthLimit,
    ContractCreationCollision,
)
from evm import precompiles

from evm.vm.message import (
    Message,
)
from evm.vm.computation import (
    Computation,
)

from evm.utils.address import (
    force_bytes_to_address,
    generate_contract_address,
)
from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.utils.keccak import (
    keccak,
)

from .opcodes import FRONTIER_OPCODES
from .blocks import FrontierBlock
from .validation import validate_frontier_transaction
from .headers import (
    create_frontier_header_from_parent,
    configure_frontier_header,
)


FRONTIER_PRECOMPILES = {
    force_bytes_to_address(b'\x01'): precompiles.ecrecover,
    force_bytes_to_address(b'\x02'): precompiles.sha256,
    force_bytes_to_address(b'\x03'): precompiles.ripemd160,
    force_bytes_to_address(b'\x04'): precompiles.identity,
}


def _execute_frontier_transaction(vm, transaction):
    #
    # 1) Pre Computation
    #

    # Validate the transaction
    transaction.validate()

    vm.validate_transaction(transaction)

    gas_fee = transaction.gas * transaction.gas_price
    with vm.state_db() as state_db:
        # Buy Gas
        state_db.delta_balance(transaction.sender, -1 * gas_fee)

        # Increment Nonce
        state_db.increment_nonce(transaction.sender)

        # Setup VM Message
        message_gas = transaction.gas - transaction.intrensic_gas

        if transaction.to == constants.CREATE_CONTRACT_ADDRESS:
            contract_address = generate_contract_address(
                transaction.sender,
                state_db.get_nonce(transaction.sender) - 1,
            )
            data = b''
            code = transaction.data
        else:
            contract_address = None
            data = transaction.data
            code = state_db.get_code(transaction.to)

    vm.logger.info(
        (
            "TRANSACTION: sender: %s | to: %s | value: %s | gas: %s | "
            "gas-price: %s | s: %s | r: %s | v: %s | data-hash: %s"
        ),
        encode_hex(transaction.sender),
        encode_hex(transaction.to),
        transaction.value,
        transaction.gas,
        transaction.gas_price,
        transaction.s,
        transaction.r,
        transaction.v,
        encode_hex(keccak(transaction.data)),
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
        with vm.state_db(read_only=True) as state_db:
            is_collision = state_db.account_has_code_or_nonce(contract_address)

        if is_collision:
            # The address of the newly created contract has *somehow* collided
            # with an existing contract address.
            computation = Computation(vm, message)
            computation.error = ContractCreationCollision(
                "Address collision while creating contract: {0}".format(
                    encode_hex(contract_address),
                )
            )
            vm.logger.debug(
                "Address collision while creating contract: %s",
                encode_hex(contract_address),
            )
        else:
            computation = vm.apply_create_message(message)
    else:
        computation = vm.apply_message(message)

    #
    # 2) Post Computation
    #
    # Self Destruct Refunds
    num_deletions = len(computation.get_accounts_for_deletion())
    if num_deletions:
        computation.gas_meter.refund_gas(constants.REFUND_SELFDESTRUCT * num_deletions)

    # Gas Refunds
    gas_remaining = computation.get_gas_remaining()
    gas_refunded = computation.get_gas_refund()
    gas_used = transaction.gas - gas_remaining
    gas_refund = min(gas_refunded, gas_used // 2)
    gas_refund_amount = (gas_refund + gas_remaining) * transaction.gas_price

    if gas_refund_amount:
        vm.logger.debug(
            'TRANSACTION REFUND: %s -> %s',
            gas_refund_amount,
            encode_hex(message.sender),
        )

        with vm.state_db() as state_db:
            state_db.delta_balance(message.sender, gas_refund_amount)

    # Miner Fees
    transaction_fee = (transaction.gas - gas_remaining - gas_refund) * transaction.gas_price
    vm.logger.debug(
        'TRANSACTION FEE: %s -> %s',
        transaction_fee,
        encode_hex(vm.block.header.coinbase),
    )
    with vm.state_db() as state_db:
        state_db.delta_balance(vm.block.header.coinbase, transaction_fee)

    # Process Self Destructs
    with vm.state_db() as state_db:
        for account, beneficiary in computation.get_accounts_for_deletion():
            # TODO: need to figure out how we prevent multiple selfdestructs from
            # the same account and if this is the right place to put this.
            vm.logger.debug('DELETING ACCOUNT: %s', encode_hex(account))

            # TODO: this balance setting is likely superflous and can be
            # removed since `delete_account` does this.
            state_db.set_balance(account, 0)
            state_db.delete_account(account)

    return computation


def _apply_frontier_message(vm, message):
    snapshot = vm.snapshot()

    if message.depth > constants.STACK_DEPTH_LIMIT:
        raise StackDepthLimit("Stack depth limit reached")

    if message.should_transfer_value and message.value:
        with vm.state_db() as state_db:
            sender_balance = state_db.get_balance(message.sender)

            if sender_balance < message.value:
                raise InsufficientFunds(
                    "Insufficient funds: {0} < {1}".format(sender_balance, message.value)
                )

            state_db.delta_balance(message.sender, -1 * message.value)
            state_db.delta_balance(message.storage_address, message.value)

        vm.logger.debug(
            "TRANSFERRED: %s from %s -> %s",
            message.value,
            encode_hex(message.sender),
            encode_hex(message.storage_address),
        )

    with vm.state_db() as state_db:
        state_db.touch_account(message.storage_address)

    computation = vm.apply_computation(message)

    if computation.error:
        vm.revert(snapshot)
    else:
        vm.commit(snapshot)

    return computation


def _apply_frontier_create_message(vm, message):
    computation = vm.apply_message(message)

    if computation.error:
        return computation
    else:
        contract_code = computation.output

        if contract_code:
            contract_code_gas_fee = len(contract_code) * constants.GAS_CODEDEPOSIT
            try:
                computation.gas_meter.consume_gas(
                    contract_code_gas_fee,
                    reason="Write contract code for CREATE",
                )
            except OutOfGas:
                computation.output = b''
            else:
                vm.logger.debug(
                    "SETTING CODE: %s -> length: %s | hash: %s",
                    encode_hex(message.storage_address),
                    len(contract_code),
                    encode_hex(keccak(contract_code))
                )
                with vm.state_db() as state_db:
                    state_db.set_code(message.storage_address, contract_code)
        return computation


FrontierVM = VM.configure(
    name='FrontierVM',
    # VM logic
    opcodes=FRONTIER_OPCODES,
    # classes
    _block_class=FrontierBlock,
    _precompiles=FRONTIER_PRECOMPILES,
    # helpers
    create_header_from_parent=staticmethod(create_frontier_header_from_parent),
    configure_header=configure_frontier_header,
    # validation
    validate_transaction=validate_frontier_transaction,
    # transactions and vm messages
    execute_transaction=_execute_frontier_transaction,
    apply_create_message=_apply_frontier_create_message,
    apply_message=_apply_frontier_message,
)
