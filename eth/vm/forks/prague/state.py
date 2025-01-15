from typing import (
    Type,
)

from eth_hash.auto import (
    keccak,
)
from eth_utils import (
    to_bytes,
)
import rlp
from rlp.sedes import (
    address,
    big_endian_int,
)

from eth.abc import (
    MessageAPI,
    SignedTransactionAPI,
    TransactionExecutorAPI,
)
from eth.constants import (
    ZERO_ADDRESS,
)
from eth.exceptions import (
    CodeNotEmpty,
    VMError,
)
from eth.precompiles.ecrecover import (
    ecrecover,
)
from eth.vm.message import (
    EIP7702Message,
)
from eth.vm.forks.cancun import (
    CancunState,
)
from eth.vm.forks.cancun.state import (
    CancunTransactionExecutor,
)

from .computation import (
    PragueComputation,
)
from .constants import (
    MAGIC,
    PER_AUTH_BASE_COST,
    PER_EMPTY_ACCOUNT_BASE_COST,
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


class PragueTransactionExecutor(CancunTransactionExecutor):
    def build_evm_message(self, transaction: SignedTransactionAPI) -> MessageAPI:
        gas_fee = transaction.gas * self.vm_state.get_gas_price(transaction)
        self.vm_state.increment_nonce(transaction.sender)
        for auth in transaction.authorization_list:
            try:
                signed = Authorization(
                    auth.chain_id,
                    auth.address,
                    auth.nonce,
                    auth.y_parity,
                    auth.r,
                    auth.s,
                )
                # authority = ecrecover(keccak(
                #     MAGIC || rlp([chain_id, address, nonce])), y_parity, r, s]
                # ))
                to_recover = MAGIC + rlp.encode(signed)
                authority = ecrecover(keccak(to_recover))
                self.vm_state.mark_address_warm(authority)
                if self.vm_state.get_code(authority) != b"":  # or already delegated
                    raise CodeNotEmpty(f"Code at address: {authority} was not empty")
                if self.vm_state.get_nonce(authority) != auth.nonce:
                    raise VMError(
                        "The nonce of the authority address needs to match "
                        "the nonce passed in."
                    )
                # if authority is not in the trie, verify nonce == 0
                # Add PER_EMPTY_ACCOUNT_BASE_COST - PER_AUTH_BASE_COST gas to the
                # global counter if authority exists
                # This might belong in the computation instead
                if self.vm_state.account_exists(authority):
                    gas_fee = gas_fee + (
                        PER_EMPTY_ACCOUNT_BASE_COST - PER_AUTH_BASE_COST
                    )
                    self.vm_state.delta_balance(authority, -1 * gas_fee)
                if auth.address == ZERO_ADDRESS:
                    empty_code_hash = to_bytes(
                        hexstr="0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"  # noqa: E501
                    )
                    self.vm_state.set_code(auth.address, empty_code_hash)

                delegation = "0xef0100" + auth.address
                self.vm_state.set_code(authority, delegation)
                self.vm_state.increment_nonce(authority)
            except VMError:
                # if anything fails, stop processing immediately
                # and move to the next auth. Gas rollback?
                pass

            return EIP7702Message(  # return a message for each authorization?
                gas=message_gas,
                to=transaction.to,
                sender=transaction.sender,
                value=transaction.value,
                data=data,
                code=code,
                create_address=contract_address,
                code_address=auth.address,
                authority=authority,
            )


class PragueState(CancunState):
    computation_class = PragueComputation
    transaction_executor_class: Type[TransactionExecutorAPI] = PragueTransactionExecutor
