from evm.vm import BaseEVM

from evm import constants
from evm.exceptions import (
    OutOfGas,
)

from evm.utils.hexidecimal import (
    encode_hex,
)

from .opcodes import HOMESTEAD_OPCODES
from .blocks import OpenHomesteadBlock
from .validation import validate_homestead_transaction


def _apply_homestead_create_message(evm, message):
    if evm.block.state_db.account_exists(message.storage_address):
        evm.block.state_db.set_nonce(message.storage_address, 0)
        evm.block.state_db.set_code(message.storage_address, b'')
        evm.block.state_db.delete_storage(message.storage_address)

    if message.sender != message.origin:
        evm.block.state_db.increment_nonce(message.sender)

    snapshot = evm.snapshot()

    computation = evm.apply_message(message)

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
                # Different from Frontier: reverts state on gas failure while
                # writing contract code.
                computation.error = err
                evm.revert(snapshot)
            else:
                if evm.logger:
                    evm.logger.debug(
                        "SETTING CODE: %s -> %s",
                        encode_hex(message.storage_address),
                        contract_code,
                    )
                computation.state_db.set_code(message.storage_address, contract_code)
        return computation


HomesteadEVM = BaseEVM.configure(
    name='HomesteadEVM',
    opcodes=HOMESTEAD_OPCODES,
    block_class=OpenHomesteadBlock,
    # method overrides
    validate_transaction=validate_homestead_transaction,
    apply_create_message=_apply_homestead_create_message,
)
