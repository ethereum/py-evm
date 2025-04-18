from typing import (
    Any,
    Optional,
    Tuple,
    Type,
    cast,
)

from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
    ValidationError,
    encode_hex,
    keccak,
)

from eth._utils.address import (
    generate_contract_address,
)
from eth._utils.calculations import (
    fake_exponential,
)
from eth.abc import (
    ComputationAPI,
    MessageAPI,
    SignedTransactionAPI,
    StateAPI,
    TransactionContextAPI,
    TransactionExecutorAPI,
    TransactionFieldsAPI,
    TransientStorageAPI,
)
from eth.constants import (
    CREATE_CONTRACT_ADDRESS,
)
from eth.typing import (
    JournalDBCheckpoint,
)
from eth.vm.forks.shanghai import (
    ShanghaiState,
)
from eth.vm.transient_storage import (
    TransientStorage,
)

from ...message import (
    Message,
)
from ..shanghai.state import (
    ShanghaiTransactionExecutor,
)
from .computation import (
    CancunComputation,
)
from .constants import (
    BEACON_ROOTS_ADDRESS,
    BEACON_ROOTS_CONTRACT_CODE,
    BLOB_BASE_FEE_UPDATE_FRACTION,
    BLOB_TX_TYPE,
    GAS_PER_BLOB,
    MIN_BLOB_BASE_FEE,
    VERSIONED_HASH_VERSION_KZG,
)
from .transaction_context import (
    CancunTransactionContext,
)
from .transactions import (
    BlobTransaction,
)


def get_total_blob_gas(transaction: TransactionFieldsAPI) -> int:
    try:
        return GAS_PER_BLOB * len(transaction.blob_versioned_hashes)  # type: ignore
    except (AttributeError, NotImplementedError):
        return 0


class CancunTransactionExecutor(ShanghaiTransactionExecutor):
    def __call__(self, *args: Any, **kwargs: Any) -> ComputationAPI:
        ret = super().__call__(*args, **kwargs)
        self.vm_state.clear_transient_storage()
        return ret

    def calc_data_fee(self, transaction: BlobTransaction) -> int:
        return get_total_blob_gas(transaction) * self.vm_state.blob_base_fee

    def build_evm_message(self, transaction: SignedTransactionAPI) -> MessageAPI:
        # deduct from sender's balance
        london_gas_fee = transaction.gas * self.vm_state.get_gas_price(transaction)
        blob_data_fee = (
            self.calc_data_fee(cast(BlobTransaction, transaction))
            if transaction.type_id == BLOB_TX_TYPE
            else 0
        )
        self.vm_state.delta_balance(
            transaction.sender, -1 * (london_gas_fee + blob_data_fee)
        )

        # increment sender nonce
        self.vm_state.increment_nonce(transaction.sender)

        msg_refund = self.calc_message_refund(transaction)
        message_gas = transaction.gas - transaction.intrinsic_gas

        if transaction.to == CREATE_CONTRACT_ADDRESS:
            contract_address = generate_contract_address(
                transaction.sender,
                self.vm_state.get_nonce(transaction.sender) - 1,
            )
            data = b""
            code = transaction.data
            is_delegation = False
        else:
            contract_address = None
            data = transaction.data
            code, delegation_address = self.get_code_at_address(transaction.to)
            is_delegation = delegation_address is not None

        self.vm_state.logger.debug2(
            f"TRANSACTION: {repr(transaction)}; "
            f"sender: {encode_hex(transaction.sender)} | "
            f"to: {encode_hex(transaction.to)} | "
            f"data-hash: {encode_hex(keccak(transaction.data))} | "
            f"gas: {transaction.gas} | "
            f"code: {encode_hex(code)} | "
        )

        message = Message(
            gas=message_gas,
            to=transaction.to,
            sender=transaction.sender,
            value=transaction.value,
            data=data,
            code=code,
            create_address=contract_address,
            refund=msg_refund,
            is_delegation=is_delegation,
        )
        return message

    def calc_message_refund(self, transaction: SignedTransactionAPI) -> int:
        """
        Calculate any initial refunds from message pre-processing. This becomes relevant
        in Prague.
        """
        return 0

    def get_code_at_address(
        self, code_address: Address
    ) -> Tuple[bytes, Optional[Address]]:
        """
        Return the code at the given address and a delegation address if the code is a
        delegation designation. Returns ``None`` until Prague.
        """
        return self.vm_state.get_code(code_address), None


class CancunState(ShanghaiState):
    computation_class = CancunComputation
    transaction_context_class: Type[TransactionContextAPI] = CancunTransactionContext
    transaction_executor_class: Type[TransactionExecutorAPI] = CancunTransactionExecutor

    _transient_storage_class: Type[TransientStorageAPI] = TransientStorage
    _transient_storage: TransientStorageAPI = None

    def set_system_contracts(self) -> None:
        super().set_system_contracts()
        if not self.get_code(BEACON_ROOTS_ADDRESS) != BEACON_ROOTS_CONTRACT_CODE:
            self.set_code(BEACON_ROOTS_ADDRESS, BEACON_ROOTS_CONTRACT_CODE)

    @property
    def transient_storage(self) -> TransientStorageAPI:
        if self._transient_storage is None:
            self._transient_storage = self._transient_storage_class()

        return self._transient_storage

    def clear_transient_storage(self) -> None:
        self.transient_storage.clear()

    def get_transient_storage(self, address: Address, slot: int) -> bytes:
        return self.transient_storage.get_transient_storage(address, slot)

    def set_transient_storage(self, address: Address, slot: int, value: bytes) -> None:
        return self.transient_storage.set_transient_storage(address, slot, value)

    def snapshot(self) -> Tuple[Hash32, JournalDBCheckpoint]:
        state_root, checkpoint = super().snapshot()
        self.transient_storage.record(checkpoint)
        return state_root, checkpoint

    def commit(self, snapshot: Tuple[Hash32, JournalDBCheckpoint]) -> None:
        super().commit(snapshot)
        _, checkpoint = snapshot
        self.transient_storage.commit(checkpoint)

    def revert(self, snapshot: Tuple[Hash32, JournalDBCheckpoint]) -> None:
        super().revert(snapshot)
        _, checkpoint = snapshot
        self.transient_storage.discard(checkpoint)

    def get_transaction_context(
        self: StateAPI, transaction: SignedTransactionAPI
    ) -> TransactionContextAPI:
        context = super().get_transaction_context(transaction)  # type: ignore
        if hasattr(transaction, "type_id") and transaction.type_id == BLOB_TX_TYPE:
            # if the transaction is a blob transaction, expose blob versioned hashes
            # through the transaction context
            context._blob_versioned_hashes = transaction.blob_versioned_hashes  # type: ignore  # noqa: E501
        return context

    @property
    def blob_base_fee(self) -> int:
        excess_blob_gas = self.execution_context.excess_blob_gas
        return fake_exponential(
            MIN_BLOB_BASE_FEE, excess_blob_gas, BLOB_BASE_FEE_UPDATE_FRACTION
        )

    def validate_transaction(self, transaction: SignedTransactionAPI) -> None:
        super().validate_transaction(transaction)

        # modify the check for sufficient balance
        max_total_fee = transaction.gas * transaction.max_fee_per_gas
        if transaction.type_id == BLOB_TX_TYPE:
            max_total_fee += (
                get_total_blob_gas(transaction) * transaction.max_fee_per_blob_gas
            )
        if self.get_balance(transaction.sender) < max_total_fee:
            raise ValidationError("Sender has insufficient funds for blob fee.")

        # add validity logic specific to blob txs
        if transaction.type_id == BLOB_TX_TYPE:
            # there must be at least one blob
            if len(transaction.blob_versioned_hashes) == 0:
                raise ValidationError(
                    "Blob transaction must contain at least one blob."
                )

            # all versioned blob hashes must start with VERSIONED_HASH_VERSION_KZG
            for h in transaction.blob_versioned_hashes:
                if h[:1] != VERSIONED_HASH_VERSION_KZG:
                    raise ValidationError(
                        "Blob versioned hash does not start with expected "
                        f"KZG version: {VERSIONED_HASH_VERSION_KZG!r}"
                    )

            # ensure that the user was willing to at least pay the current
            # blob base fee
            if transaction.max_fee_per_blob_gas < self.blob_base_fee:
                raise ValidationError(
                    "Blob transaction must pay at least the current blob base fee."
                )
