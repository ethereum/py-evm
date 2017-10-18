from evm import constants
from evm.exceptions import (
    OutOfGas,
)

from evm.utils.hexadecimal import (
    encode_hex,
)
from evm.utils.keccak import (
    keccak,
)

from ..frontier import FrontierVM

from .opcodes import HOMESTEAD_OPCODES
from .blocks import HomesteadBlock
from .validation import validate_homestead_transaction
from .headers import (
    create_homestead_header_from_parent,
    configure_homestead_header,
)


def _apply_homestead_create_message(vm, message):
    snapshot = vm.snapshot()

    computation = vm.apply_message(message)

    if computation.error:
        vm.revert(snapshot)
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
                vm.revert(snapshot)
            else:
                if vm.logger:
                    vm.logger.debug(
                        "SETTING CODE: %s -> length: %s | hash: %s",
                        encode_hex(message.storage_address),
                        len(contract_code),
                        encode_hex(keccak(contract_code))
                    )

                with vm.state_db() as state_db:
                    state_db.set_code(message.storage_address, contract_code)
                vm.commit(snapshot)
        else:
            vm.commit(snapshot)
        return computation


class MetaHomesteadVM(FrontierVM):
    support_dao_fork = True
    dao_fork_block_number = constants.DAO_FORK_BLOCK_NUMBER


HomesteadVM = MetaHomesteadVM.configure(
    name='HomesteadVM',
    opcodes=HOMESTEAD_OPCODES,
    _block_class=HomesteadBlock,
    # method overrides
    validate_transaction=validate_homestead_transaction,
    apply_create_message=_apply_homestead_create_message,
    create_header_from_parent=staticmethod(create_homestead_header_from_parent),
    configure_header=configure_homestead_header,
)
