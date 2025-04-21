from typing import (
    Optional,
    Tuple,
    Type,
)

from eth_keys import (
    keys,
)
from eth_typing import (
    Address,
)
import rlp

from eth import (
    constants,
)
from eth._utils.address import (
    force_bytes_to_address,
)
from eth._utils.state import (
    code_is_delegation_designation,
)
from eth.abc import (
    SignedTransactionAPI,
    TransactionExecutorAPI,
)
from eth.constants import (
    GAS_TX,
)
from eth.vm.forks.cancun import (
    CancunState,
)
from eth.vm.forks.cancun.constants import (
    MIN_BLOB_BASE_FEE,
)
from eth.vm.forks.cancun.state import (
    CancunTransactionExecutor,
    fake_exponential,
)
from eth.vm.forks.prague.constants import (
    BLOB_BASE_FEE_UPDATE_FRACTION_PRAGUE,
    DELEGATION_DESIGNATION_PREFIX,
    HISTORY_STORAGE_ADDRESS,
    HISTORY_STORAGE_CONTRACT_CODE,
    MAGIC,
    PER_AUTH_BASE_COST,
    PER_EMPTY_ACCOUNT_BASE_COST,
    SET_CODE_TRANSACTION_TYPE,
    STANDARD_TOKEN_COST,
    TOTAL_COST_FLOOR_PER_TOKEN,
)

from .computation import (
    PragueComputation,
)


class PragueTransactionExecutor(CancunTransactionExecutor):
    def calc_message_refund(self, transaction: SignedTransactionAPI) -> int:
        message_refund = super().calc_message_refund(transaction)
        if transaction.type_id == SET_CODE_TRANSACTION_TYPE:
            authorizations_refund = self.vm_state.process_set_code_authorizations(
                transaction
            )
            message_refund += authorizations_refund
        return message_refund

    def get_code_at_address(
        self, code_address: Address
    ) -> Tuple[bytes, Optional[Address]]:
        """
        Get the code at the given address. If the code is a delegation designation,
        return the code at the delegation address instead and return the
        delegation address.
        """
        code = self.vm_state.get_code(code_address)
        if code_is_delegation_designation(code):
            delegation_address = force_bytes_to_address(code[3:])
            self.vm_state.mark_address_warm(delegation_address)
            return self.vm_state.get_code(delegation_address), delegation_address

        return code, None

    @staticmethod
    def calc_data_floor_gas(
        transaction: SignedTransactionAPI,
        gas_used: int,
        gas_refund: int,
    ) -> int:
        # eip7623 data floor cost
        zeros_in_data = transaction.data.count(b"\x00")
        non_zeros_in_data = len(transaction.data) - zeros_in_data
        tokens_in_calldata = zeros_in_data + (non_zeros_in_data * STANDARD_TOKEN_COST)

        eip7623_gas = GAS_TX + (TOTAL_COST_FLOOR_PER_TOKEN * tokens_in_calldata)
        data_floor_diff = eip7623_gas - (gas_used - gas_refund)

        # return any extra gas needed to reach the floor cost
        return max(data_floor_diff, 0)


class PragueState(CancunState):
    computation_class = PragueComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = PragueTransactionExecutor

    def set_system_contracts(self) -> None:
        super().set_system_contracts()
        if not self.get_code(HISTORY_STORAGE_ADDRESS) != HISTORY_STORAGE_CONTRACT_CODE:
            self.set_code(HISTORY_STORAGE_ADDRESS, HISTORY_STORAGE_CONTRACT_CODE)

    @property
    def blob_base_fee(self) -> int:
        excess_blob_gas = self.execution_context.excess_blob_gas
        return fake_exponential(
            MIN_BLOB_BASE_FEE,
            excess_blob_gas,
            BLOB_BASE_FEE_UPDATE_FRACTION_PRAGUE,
        )

    def process_set_code_authorizations(self, transaction: SignedTransactionAPI) -> int:
        authorizations_refund = 0
        for auth in transaction.authorization_list:
            try:
                # (1, 2, 3).
                # - verify chain_id is 0 or chain's current id
                # - verify nonce < 2**64 - 1
                # - verify s <= secp256k1n/2
                auth.validate(self.execution_context.chain_id)

                # 3. authority = ecrecover(msg, y_parity, r, s)
                encoded = rlp.encode([auth.chain_id, auth.address, auth.nonce])
                msg = MAGIC + encoded
                signature = keys.Signature(vrs=(auth.y_parity, auth.r, auth.s))
                public_key = signature.recover_public_key_from_msg(msg)
                authority = Address(public_key.to_canonical_address())

                # 4. add authority to accessed addresses
                self.mark_address_warm(authority)

                # 5. verify the code is either empty or already delegated
                code = self.get_code(authority)
                if code != b"" and not code_is_delegation_designation(code):
                    continue

                # 6. verify the nonce of authority is equal to nonce
                if self.account_exists(authority):
                    if self.get_nonce(authority) != auth.nonce:
                        continue

                    # 7. add refund to the global counter
                    refund = PER_EMPTY_ACCOUNT_BASE_COST - PER_AUTH_BASE_COST
                    authorizations_refund += refund
                else:
                    # 6. if authority is not in the trie, verify ``auth.nonce==0``
                    if auth.nonce != 0:
                        continue

                # 8. set the code of authority to be the delegation designation
                if auth.address == constants.ZERO_ADDRESS:
                    self.delete_code(authority)  # special case @ zero address
                else:
                    self.set_code(
                        authority, DELEGATION_DESIGNATION_PREFIX + auth.address
                    )

                # 9. increment authority nonce
                self.increment_nonce(authority)
            except Exception as e:
                # with any exception, continue to the next authorization and log
                if self.logger.show_debug2:
                    self.logger.debug2("Invalid authorization: %s", e)

        return authorizations_refund
