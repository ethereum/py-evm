from typing import (
    Type,
)

from eth_keys import (
    keys,
)
from eth_keys.exceptions import (
    BadSignature,
)
from eth_typing import (
    Address,
)
from eth_utils.exceptions import (
    ValidationError,
)
import rlp
from rlp.sedes import (
    big_endian_int,
)

from eth import (
    constants,
)
from eth._utils.address import (
    force_bytes_to_address,
)

from eth.abc import (
    ComputationAPI,
    MessageAPI,
    SignedTransactionAPI,
    StateAPI,
    TransactionContextAPI,
    TransactionExecutorAPI,
)
from eth.constants import (
    GAS_TX,
)
from eth.exceptions import (
    CodeNotEmpty,
    VMError,
)
from eth.rlp.sedes import (
    address,
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
    DELEGATION_DESIGNATION,
    HISTORY_STORAGE_ADDRESS,
    HISTORY_STORAGE_CONTRACT_CODE,
    PER_AUTH_BASE_COST,
    PER_EMPTY_ACCOUNT_BASE_COST,
    SET_CODE_TRANSACTION_TYPE,
    STANDARD_TOKEN_COST,
    TOTAL_COST_FLOOR_PER_TOKEN,
)

from .computation import (
    PragueComputation,
)
from .transaction_context import (
    PragueTransactionContext,
)


class Authorization(rlp.Serializable):
    fields = (
        ("chain_id", big_endian_int),
        ("account", address),
        ("nonce", big_endian_int),
        ("y_parity", big_endian_int),
        ("r", big_endian_int),
        ("s", big_endian_int),
    )

    def __init__(
        self,
        chain_id: int,
        account: Address,
        nonce: int,
        y_parity: int,
        r: int,
        s: int,
    ) -> None:
        super().__init__(
            chain_id=chain_id,
            account=account,
            nonce=nonce,
            y_parity=y_parity,
            r=r,
            s=s,
        )


def _has_delegation_prefix(code: bytes) -> bool:
    return code[:3] == DELEGATION_DESIGNATION


class PragueTransactionExecutor(CancunTransactionExecutor):
    def validate_eip7623_calldata_cost(
        self,
        transaction: SignedTransactionAPI,
        computation: ComputationAPI,
    ) -> None:
        gas_remaining = computation.get_gas_remaining()
        gas_used = transaction.gas - gas_remaining
        gas_refund = self.calculate_gas_refund(computation, gas_used)
        total_gas_used = transaction.gas - gas_remaining - gas_refund

        zeros_in_data = transaction.data.count(b"\x00")
        non_zeros_in_data = len(transaction.data) - zeros_in_data
        tokens_in_calldata = zeros_in_data + (non_zeros_in_data * STANDARD_TOKEN_COST)

        eip7623_gas = GAS_TX + (TOTAL_COST_FLOOR_PER_TOKEN * tokens_in_calldata)

        data_floor_diff = eip7623_gas - total_gas_used
        if data_floor_diff > 0:
            if gas_refund >= data_floor_diff:
                # pull gas out of refund to cover the data floor diff
                computation.return_gas(data_floor_diff)
                computation.refund_gas(-data_floor_diff)

            computation.consume_gas(data_floor_diff, "EIP-7623 calldata gas floor")

    def build_evm_message(self, transaction: SignedTransactionAPI) -> MessageAPI:
        msg = super().build_evm_message(transaction)
        is_delegation = hasattr(transaction, "authorization_list")
        msg.is_delegation = is_delegation
        return msg

    def build_computation(
        self, message: MessageAPI, transaction: SignedTransactionAPI
    ) -> ComputationAPI:
        if hasattr(transaction, "authorization_list"):
            for auth in transaction.authorization_list:
                self.vm_state.process_authorization(
                    auth, self.vm_state.get_computation(message, self)
                )
        return super().build_computation(message, transaction)

    def finalize_computation(
        self, transaction: SignedTransactionAPI, computation: ComputationAPI
    ) -> ComputationAPI:
        self.validate_eip7623_calldata_cost(transaction, computation)
        return super().finalize_computation(transaction, computation)


class PragueState(CancunState):
    computation_class = PragueComputation
    transaction_context_class: Type[TransactionContextAPI] = PragueTransactionContext
    transaction_executor_class: Type[TransactionExecutorAPI] = PragueTransactionExecutor

    def set_system_contracts(self) -> None:
        super().set_system_contracts()
        if not self.get_code(HISTORY_STORAGE_ADDRESS) != HISTORY_STORAGE_CONTRACT_CODE:
            self.set_code(HISTORY_STORAGE_ADDRESS, HISTORY_STORAGE_CONTRACT_CODE)

    def get_transaction_context(
        self: StateAPI, transaction: SignedTransactionAPI
    ) -> TransactionContextAPI:
        context = super().get_transaction_context(transaction)  # type: ignore
        if (
            hasattr(transaction, "type_id")
            and transaction.type_id == SET_CODE_TRANSACTION_TYPE
        ):
            # if the transaction is a set code transaction, expose authorization lists
            # through the transaction context
            context._authorization_list = transaction.authorization_list
        return context

    @property
    def blob_base_fee(self) -> int:
        excess_blob_gas = self.execution_context.excess_blob_gas
        return fake_exponential(
            MIN_BLOB_BASE_FEE,
            excess_blob_gas,
            BLOB_BASE_FEE_UPDATE_FRACTION_PRAGUE,
        )

    def process_authorization(
        self, auth: Authorization, computation: ComputationAPI
    ) -> None:
        try:
            # 1. verify chain_id is 0 or chain's current id
            chain_id_current_or_zero = (
                auth.chain_id == self.execution_context.chain_id or auth.chain_id == 0
            )
            if not chain_id_current_or_zero:
                raise VMError("chain id must match current chain id or be 0")
            # authority = ecrecover(keccak(
            #     MAGIC || rlp([chain_id, address, nonce])), y_parity, r, s]
            # ))
            magic = b"\x05"
            encoded = rlp.encode([auth.chain_id, auth.account, auth.nonce])
            message = magic + encoded
            vrs = (auth.y_parity, auth.r, auth.s)
            signature = keys.Signature(vrs=vrs)
            public_key = signature.recover_public_key_from_msg(message)
            authority = Address(public_key.to_canonical_address())
            # 4. Add authority to accessed addresses
            self.mark_address_warm(authority)

            code = self.get_code(authority)
            # 5. verify the code is either empty or already delegated
            if code != b"" and not _has_delegation_prefix(code):
                raise CodeNotEmpty(
                    f"Code at address: {authority!r} was not empty and not delegated"
                )

            # 6. Verify the nonce of authority is equal to nonce. if authority is not
            #    in the trie, verify nonce == 0
            # 7. Add PER_EMPTY_ACCOUNT_BASE_COST - PER_AUTH_BASE_COST gas to the
            #    global refund counter if authority exists
            if self.account_exists(authority):
                if self.get_nonce(authority) != auth.nonce:
                    print("authority nonce: ", self.get_nonce(authority))
                    print("auth.nonce: ", auth.nonce)
                    raise VMError(
                        "The nonce of the authority address needs to match "
                        "the nonce passed in."
                    )
                refund = PER_EMPTY_ACCOUNT_BASE_COST - PER_AUTH_BASE_COST
                computation.refund_gas(refund)
            elif not self.account_exists(authority):
                # if authority is not in the trie, verify nonce == 0
                if self.get_nonce(authority) != 0:
                    raise VMError(f"Authority {authority!r} has a nonce")

            # 8. Set the code of authority to be delegation
            if auth.account == constants.ZERO_ADDRESS:
                self.set_code(authority, constants.EMPTY_SHA3)
            delegation = DELEGATION_DESIGNATION + auth.account
            self.set_code(authority, delegation)

            if _has_delegation_prefix(self.get_code(force_bytes_to_address(code[3:]))):
                raise VMError("Can't recursively delegate code")

            # 9. Increase nonce of authority by 1
            self.increment_nonce(authority)
        except (VMError, BadSignature, ValidationError) as e:
            # if anything fails, stop processing immediately
            # and move to the next auth. Gas rollback?
            print("there was an error!!", e)
            # pass
