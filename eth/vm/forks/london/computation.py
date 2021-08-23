from eth_utils import encode_hex, keccak

from eth import constants
from eth.abc import ComputationAPI, MessageAPI, StateAPI, TransactionContextAPI
from eth.exceptions import OutOfGas, ReservedBytesInCode
from eth.vm.forks.berlin.computation import (
    BerlinComputation,
)

from .opcodes import LONDON_OPCODES
from ..london.constants import EIP3541_RESERVED_STARTING_BYTE
from ..spurious_dragon.constants import EIP170_CODE_SIZE_LIMIT


class LondonComputation(BerlinComputation):
    """
    A class for all execution computations in the ``London`` fork.
    Inherits from :class:`~eth.vm.forks.berlin.BerlinComputation`
    """
    opcodes = LONDON_OPCODES

    @classmethod
    def apply_create_message(
        cls,
        state: StateAPI,
        message: MessageAPI,
        transaction_context: TransactionContextAPI
    ) -> ComputationAPI:

        snapshot = state.snapshot()

        # EIP161 nonce incrementation
        state.increment_nonce(message.storage_address)

        computation = cls.apply_message(state, message, transaction_context)

        if computation.is_error:
            state.revert(snapshot)
            return computation
        else:
            contract_code = computation.output

            if contract_code and len(contract_code) >= EIP170_CODE_SIZE_LIMIT:
                computation.error = OutOfGas(
                    f"Contract code size exceeds EIP170 limit of {EIP170_CODE_SIZE_LIMIT}."
                    f" Got code of size: {len(contract_code)}"
                )
                state.revert(snapshot)
            elif contract_code:
                contract_code_gas_cost = len(contract_code) * constants.GAS_CODEDEPOSIT
                try:
                    computation.consume_gas(
                        contract_code_gas_cost,
                        reason="Write contract code for CREATE / CREATE2",
                    )
                except OutOfGas as err:
                    computation.error = err
                    state.revert(snapshot)
                else:
                    if contract_code[:1] == EIP3541_RESERVED_STARTING_BYTE:
                        # As per EIP-3541, gas is still consumed on a revert of this nature
                        state.revert(snapshot)
                        raise ReservedBytesInCode(
                            "Contract code begins with EIP3541 reserved byte '0xEF'."
                        )
                    else:
                        if cls.logger:
                            cls.logger.debug2(
                                "SETTING CODE: %s -> length: %s | hash: %s",
                                encode_hex(message.storage_address),
                                len(contract_code),
                                encode_hex(keccak(contract_code))
                            )

                        state.set_code(message.storage_address, contract_code)
                        state.commit(snapshot)
            else:
                state.commit(snapshot)
            return computation
