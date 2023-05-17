from typing import (
    Dict,
    Sequence,
    Tuple,
    Type,
    Union,
)

from cached_property import (
    cached_property,
)
from eth_keys.datatypes import (
    PrivateKey,
)
from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
    to_bytes,
)
import rlp
from rlp.sedes import (
    CountableList,
    big_endian_int,
    binary,
)

from eth._utils.transactions import (
    calculate_intrinsic_gas,
    create_transaction_signature,
    extract_transaction_sender,
    validate_transaction_signature,
)
from eth.abc import (
    ReceiptAPI,
    SignedTransactionAPI,
    TransactionDecoderAPI,
)
from eth.constants import (
    CREATE_CONTRACT_ADDRESS,
)
from eth.rlp.logs import (
    Log,
)
from eth.rlp.receipts import (
    Receipt,
)
from eth.rlp.sedes import (
    address,
)
from eth.rlp.transactions import (
    SignedTransactionMethods,
)
from eth.validation import (
    validate_canonical_address,
    validate_is_bytes,
    validate_is_transaction_access_list,
    validate_uint64,
    validate_uint256,
)
from eth.vm.forks.berlin.constants import (
    ACCESS_LIST_ADDRESS_COST_EIP_2930,
    ACCESS_LIST_STORAGE_KEY_COST_EIP_2930,
    ACCESS_LIST_TRANSACTION_TYPE,
)
from eth.vm.forks.berlin.transactions import (
    AccessListPayloadDecoder,
    AccountAccesses,
    BerlinLegacyTransaction,
    BerlinTransactionBuilder,
    BerlinUnsignedLegacyTransaction,
    TypedTransaction,
)
from eth.vm.forks.istanbul.transactions import (
    ISTANBUL_TX_GAS_SCHEDULE,
)

from .constants import (
    DYNAMIC_FEE_TRANSACTION_TYPE,
)
from .receipts import (
    LondonReceiptBuilder,
)


class LondonLegacyTransaction(BerlinLegacyTransaction):
    pass


class LondonUnsignedLegacyTransaction(BerlinUnsignedLegacyTransaction):
    def as_signed_transaction(
        self, private_key: PrivateKey, chain_id: int = None
    ) -> LondonLegacyTransaction:
        v, r, s = create_transaction_signature(self, private_key, chain_id=chain_id)
        return LondonLegacyTransaction(
            nonce=self.nonce,
            gas_price=self.gas_price,
            gas=self.gas,
            to=self.to,
            value=self.value,
            data=self.data,
            v=v,
            r=r,
            s=s,
        )


class UnsignedDynamicFeeTransaction(rlp.Serializable):
    _type_id = DYNAMIC_FEE_TRANSACTION_TYPE
    fields = [
        ("chain_id", big_endian_int),
        ("nonce", big_endian_int),
        ("max_priority_fee_per_gas", big_endian_int),
        ("max_fee_per_gas", big_endian_int),
        ("gas", big_endian_int),
        ("to", address),
        ("value", big_endian_int),
        ("data", binary),
        ("access_list", CountableList(AccountAccesses)),
    ]

    @cached_property
    def _type_byte(self) -> bytes:
        return to_bytes(self._type_id)

    def get_message_for_signing(self) -> bytes:
        payload = rlp.encode(self)
        return self._type_byte + payload

    def as_signed_transaction(self, private_key: PrivateKey) -> "TypedTransaction":
        message = self.get_message_for_signing()
        signature = private_key.sign_msg(message)
        y_parity, r, s = signature.vrs

        signed_transaction = DynamicFeeTransaction(
            self.chain_id,
            self.nonce,
            self.max_priority_fee_per_gas,
            self.max_fee_per_gas,
            self.gas,
            self.to,
            self.value,
            self.data,
            self.access_list,
            y_parity,
            r,
            s,
        )
        return LondonTypedTransaction(self._type_id, signed_transaction)

    def validate(self) -> None:
        validate_uint256(self.chain_id, title="Transaction.chain_id")
        validate_uint64(self.nonce, title="Transaction.nonce")
        validate_uint256(self.max_fee_per_gas, title="Transaction.max_fee_per_gas")
        validate_uint256(
            self.max_priority_fee_per_gas, title="Transaction.max_priority_fee_per_gas"
        )
        validate_uint256(self.gas, title="Transaction.gas")
        if self.to != CREATE_CONTRACT_ADDRESS:
            validate_canonical_address(self.to, title="Transaction.to")
        validate_uint256(self.value, title="Transaction.value")
        validate_is_bytes(self.data, title="Transaction.data")
        validate_is_transaction_access_list(self.access_list)

    def get_intrinsic_gas(self) -> int:
        return _get_dynamic_fee_txn_intrinsic_gas(self)

    @property
    def intrinsic_gas(self) -> int:
        return self.get_intrinsic_gas()


class DynamicFeeTransaction(
    rlp.Serializable, SignedTransactionMethods, SignedTransactionAPI
):
    _type_id = DYNAMIC_FEE_TRANSACTION_TYPE
    fields = [
        ("chain_id", big_endian_int),
        ("nonce", big_endian_int),
        ("max_priority_fee_per_gas", big_endian_int),
        ("max_fee_per_gas", big_endian_int),
        ("gas", big_endian_int),
        ("to", address),
        ("value", big_endian_int),
        ("data", binary),
        ("access_list", CountableList(AccountAccesses)),
        ("y_parity", big_endian_int),
        ("r", big_endian_int),
        ("s", big_endian_int),
    ]

    @property
    def gas_price(self) -> None:
        raise AttributeError(
            "Gas price is no longer available."
            "See max_priority_fee_per_gas or max_fee_per_gas"
        )

    def get_sender(self) -> Address:
        return extract_transaction_sender(self)

    def get_message_for_signing(self) -> bytes:
        unsigned = UnsignedDynamicFeeTransaction(
            self.chain_id,
            self.nonce,
            self.max_priority_fee_per_gas,
            self.max_fee_per_gas,
            self.gas,
            self.to,
            self.value,
            self.data,
            self.access_list,
        )
        payload = rlp.encode(unsigned)
        return self._type_byte + payload

    def check_signature_validity(self) -> None:
        validate_transaction_signature(self)

    @cached_property
    def _type_byte(self) -> bytes:
        return to_bytes(self._type_id)

    @cached_property
    def hash(self) -> Hash32:
        raise NotImplementedError("Call hash() on the TypedTransaction instead")

    def get_intrinsic_gas(self) -> int:
        return _get_dynamic_fee_txn_intrinsic_gas(self)

    def encode(self) -> bytes:
        return rlp.encode(self)

    def make_receipt(
        self,
        status: bytes,
        gas_used: int,
        log_entries: Tuple[Tuple[bytes, Tuple[int, ...], bytes], ...],
    ) -> ReceiptAPI:
        logs = [Log(address, topics, data) for address, topics, data in log_entries]
        # TypedTransaction is responsible for wrapping this into a TypedReceipt
        return Receipt(
            state_root=status,
            gas_used=gas_used,
            logs=logs,
        )


class DynamicFeePayloadDecoder(TransactionDecoderAPI):
    @classmethod
    def decode(cls, payload: bytes) -> SignedTransactionAPI:
        return rlp.decode(payload, sedes=DynamicFeeTransaction)


class LondonTypedTransaction(TypedTransaction):
    decoders: Dict[int, Type[TransactionDecoderAPI]] = {
        ACCESS_LIST_TRANSACTION_TYPE: AccessListPayloadDecoder,
        DYNAMIC_FEE_TRANSACTION_TYPE: DynamicFeePayloadDecoder,
    }
    receipt_builder = LondonReceiptBuilder


class LondonTransactionBuilder(BerlinTransactionBuilder):
    legacy_signed = LondonLegacyTransaction
    legacy_unsigned = LondonUnsignedLegacyTransaction
    typed_transaction = LondonTypedTransaction

    @classmethod
    def new_unsigned_dynamic_fee_transaction(
        cls,
        chain_id: int,
        nonce: int,
        max_priority_fee_per_gas: int,
        max_fee_per_gas: int,
        gas: int,
        to: Address,
        value: int,
        data: bytes,
        access_list: Sequence[Tuple[Address, Sequence[int]]],
    ) -> LondonTypedTransaction:
        transaction = UnsignedDynamicFeeTransaction(
            chain_id,
            nonce,
            max_priority_fee_per_gas,
            max_fee_per_gas,
            gas,
            to,
            value,
            data,
            access_list,
        )
        return transaction

    @classmethod
    def new_dynamic_fee_transaction(
        cls,
        chain_id: int,
        nonce: int,
        max_priority_fee_per_gas: int,
        max_fee_per_gas: int,
        gas: int,
        to: Address,
        value: int,
        data: bytes,
        access_list: Sequence[Tuple[Address, Sequence[int]]],
        y_parity: int,
        r: int,
        s: int,
    ) -> LondonTypedTransaction:
        transaction = DynamicFeeTransaction(
            chain_id,
            nonce,
            max_priority_fee_per_gas,
            max_fee_per_gas,
            gas,
            to,
            value,
            data,
            access_list,
            y_parity,
            r,
            s,
        )
        return LondonTypedTransaction(DYNAMIC_FEE_TRANSACTION_TYPE, transaction)


def _get_dynamic_fee_txn_intrinsic_gas(
    klass: Union[DynamicFeeTransaction, UnsignedDynamicFeeTransaction]
) -> int:
    core_gas = calculate_intrinsic_gas(ISTANBUL_TX_GAS_SCHEDULE, klass)

    num_addresses = len(klass.access_list)
    preload_address_costs = ACCESS_LIST_ADDRESS_COST_EIP_2930 * num_addresses

    num_slots = sum(len(slots) for _, slots in klass.access_list)
    preload_slot_costs = ACCESS_LIST_STORAGE_KEY_COST_EIP_2930 * num_slots

    return core_gas + preload_address_costs + preload_slot_costs
