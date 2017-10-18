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

from ..frontier import _execute_frontier_transaction
from ..homestead import HomesteadVM

from .blocks import SpuriousDragonBlock
from .opcodes import SPURIOUS_DRAGON_OPCODES
from .utils import collect_touched_accounts


def _execute_spurious_dragon_transaction(vm, transaction):
    computation = _execute_frontier_transaction(vm, transaction)

    #
    # EIP161 state clearing
    #
    touched_accounts = collect_touched_accounts(computation)

    with vm.state_db() as state_db:
        for account in touched_accounts:
            if state_db.account_exists(account) and state_db.account_is_empty(account):
                vm.logger.debug(
                    "CLEARING EMPTY ACCOUNT: %s",
                    encode_hex(account),
                )
                state_db.delete_account(account)

    return computation


def _apply_spurious_dragon_create_message(vm, message):
    snapshot = vm.snapshot()

    # EIP161 nonce incrementation
    with vm.state_db() as state_db:
        state_db.increment_nonce(message.storage_address)

    computation = vm.apply_message(message)

    if computation.error:
        vm.revert(snapshot)
        return computation
    else:
        contract_code = computation.output

        if contract_code and len(contract_code) >= constants.EIP170_CODE_SIZE_LIMIT:
            computation.error = OutOfGas(
                "Contract code size exceeds EIP170 limit of {0}.  Got code of "
                "size: {1}".format(
                    constants.EIP170_CODE_SIZE_LIMIT,
                    len(contract_code),
                )
            )
            vm.revert(snapshot)
        elif contract_code:
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


SpuriousDragonVM = HomesteadVM.configure(
    name='SpuriousDragonVM',
    # rlp classes
    _block_class=SpuriousDragonBlock,
    # opcodes
    opcodes=SPURIOUS_DRAGON_OPCODES,
    apply_create_message=_apply_spurious_dragon_create_message,
    execute_transaction=_execute_spurious_dragon_transaction,
)
