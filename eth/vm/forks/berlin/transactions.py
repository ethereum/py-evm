from typing import (
    Any,
    Dict,
    Sequence,
    Tuple,
    Type,
    Union,
    cast,
)

from cached_property import (
    cached_property,
)
from eth_hash.auto import (
    keccak,
)
from eth_keys.datatypes import (
    PrivateKey,
)
from eth_typing import (
    Address,
    Hash32,
)
from eth_utils import (
    ValidationError,
    to_bytes,
    to_int,
)
import rlp
from rlp.sedes import (
    BigEndianInt,
    Binary,
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
    DecodedZeroOrOneLayerRLP,
    ReceiptAPI,
    SignedTransactionAPI,
    TransactionBuilderAPI,
    TransactionDecoderAPI,
    UnsignedTransactionAPI,
)
from eth.constants import (
    CREATE_CONTRACT_ADDRESS,
)
from eth.exceptions import (
    UnrecognizedTransactionType,
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
from eth.vm.forks.istanbul.transactions import (
    ISTANBUL_TX_GAS_SCHEDULE,
)
from eth.vm.forks.muir_glacier.transactions import (
    MuirGlacierTransaction,
    MuirGlacierUnsignedTransaction,
)

from .constants import (
    ACCESS_LIST_ADDRESS_COST_EIP_2930,
    ACCESS_LIST_STORAGE_KEY_COST_EIP_2930,
    ACCESS_LIST_TRANSACTION_TYPE,
    VALID_TRANSACTION_TYPES,
)
from .receipts import (
    BerlinReceiptBuilder,
)


class BerlinLegacyTransaction(MuirGlacierTransaction):
    pass


class BerlinUnsignedLegacyTransaction(MuirGlacierUnsignedTransaction):
    def as_signed_transaction(
        self, private_key: PrivateKey, chain_id: int = None
    ) -> BerlinLegacyTransaction:
        v, r, s = create_transaction_signature(self, private_key, chain_id=chain_id)
        return BerlinLegacyTransaction(
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


class AccountAccesses(rlp.Serializable):
    fields = [
        ("account", address),
        ("storage_keys", CountableList(BigEndianInt(32))),
    ]


class UnsignedAccessListTransaction(rlp.Serializable):
    _type_id = ACCESS_LIST_TRANSACTION_TYPE
    fields = [
        ("chain_id", big_endian_int),
        ("nonce", big_endian_int),
        ("gas_price", big_endian_int),
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

        signed_transaction = AccessListTransaction(
            self.chain_id,
            self.nonce,
            self.gas_price,
            self.gas,
            self.to,
            self.value,
            self.data,
            self.access_list,
            y_parity,
            r,
            s,
        )
        return TypedTransaction(self._type_id, signed_transaction)

    def validate(self) -> None:
        validate_uint256(self.chain_id, title="Transaction.chain_id")
        validate_uint64(self.nonce, title="Transaction.nonce")
        validate_uint256(self.gas_price, title="Transaction.gas_price")
        validate_uint256(self.gas, title="Transaction.gas")
        if self.to != CREATE_CONTRACT_ADDRESS:
            validate_canonical_address(self.to, title="Transaction.to")
        validate_uint256(self.value, title="Transaction.value")
        validate_is_bytes(self.data, title="Transaction.data")
        validate_is_transaction_access_list(self.access_list)

    def get_intrinsic_gas(self) -> int:
        return _get_access_list_txn_intrinsic_gas(self)

    @property
    def intrinsic_gas(self) -> int:
        return self.get_intrinsic_gas()

    # Old transactions are treated as setting both max-fees as the gas price
    @property
    def max_priority_fee_per_gas(self) -> int:
        return self.gas_price

    @property
    def max_fee_per_gas(self) -> int:
        return self.gas_price


class AccessListTransaction(
    rlp.Serializable, SignedTransactionMethods, SignedTransactionAPI
):
    _type_id = ACCESS_LIST_TRANSACTION_TYPE
    fields = [
        ("chain_id", big_endian_int),
        ("nonce", big_endian_int),
        ("gas_price", big_endian_int),
        ("gas", big_endian_int),
        ("to", address),
        ("value", big_endian_int),
        ("data", binary),
        ("access_list", CountableList(AccountAccesses)),
        ("y_parity", big_endian_int),
        ("r", big_endian_int),
        ("s", big_endian_int),
    ]

    def get_sender(self) -> Address:
        return extract_transaction_sender(self)

    def get_message_for_signing(self) -> bytes:
        unsigned = UnsignedAccessListTransaction(
            self.chain_id,
            self.nonce,
            self.gas_price,
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
        return _get_access_list_txn_intrinsic_gas(self)

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

    # Old transactions are treated as setting both max-fees as the gas price
    @property
    def max_priority_fee_per_gas(self) -> int:
        return self.gas_price

    @property
    def max_fee_per_gas(self) -> int:
        return self.gas_price


class AccessListPayloadDecoder(TransactionDecoderAPI):
    @classmethod
    def decode(cls, payload: bytes) -> SignedTransactionAPI:
        return rlp.decode(payload, sedes=AccessListTransaction)


class TypedTransaction(
    SignedTransactionMethods, SignedTransactionAPI, TransactionDecoderAPI
):
    rlp_type = Binary(min_length=1)  # must have at least one byte for the type
    _inner: SignedTransactionAPI

    decoders: Dict[int, Type[TransactionDecoderAPI]] = {
        ACCESS_LIST_TRANSACTION_TYPE: AccessListPayloadDecoder,
    }
    receipt_builder = BerlinReceiptBuilder

    def __init__(self, type_id: int, proxy_target: SignedTransactionAPI) -> None:
        self.type_id = type_id
        self._inner = proxy_target

    @classmethod
    def get_payload_codec(cls, type_id: int) -> Type[TransactionDecoderAPI]:
        if type_id in cls.decoders:
            return cls.decoders[type_id]
        elif type_id in VALID_TRANSACTION_TYPES:
            raise UnrecognizedTransactionType(type_id, "Unknown transaction type")
        else:
            raise ValidationError(
                f"Cannot build typed transaction with {hex(type_id)} >= 0x80"
            )

    def encode(self) -> bytes:
        return self._type_byte + self._inner.encode()

    @classmethod
    def decode(cls, encoded: bytes) -> SignedTransactionAPI:
        type_id = to_int(encoded[0])
        payload = encoded[1:]

        payload_codec = cls.get_payload_codec(type_id)
        inner_transaction = payload_codec.decode(payload)
        return cls(type_id, inner_transaction)

    @classmethod
    def serialize(cls, obj: "TypedTransaction") -> DecodedZeroOrOneLayerRLP:
        encoded = obj.encode()
        return cls.rlp_type.serialize(encoded)

    @classmethod
    def deserialize(
        cls, encoded_unchecked: DecodedZeroOrOneLayerRLP
    ) -> SignedTransactionAPI:
        # binary checks a few basics, like the length of the bytes
        encoded = cls.rlp_type.deserialize(encoded_unchecked)
        return cls.decode(encoded)

    @cached_property
    def _type_byte(self) -> bytes:
        return to_bytes(self.type_id)

    @property
    def chain_id(self) -> int:
        return self._inner.chain_id

    @property
    def nonce(self) -> int:
        return self._inner.nonce

    @property
    def gas_price(self) -> int:
        return self._inner.gas_price

    @property
    def max_priority_fee_per_gas(self) -> int:
        return self._inner.max_priority_fee_per_gas

    @property
    def max_fee_per_gas(self) -> int:
        return self._inner.max_fee_per_gas

    @property
    def gas(self) -> int:
        return self._inner.gas

    @property
    def to(self) -> Address:
        return self._inner.to

    @property
    def value(self) -> int:
        return self._inner.value

    @property
    def data(self) -> bytes:
        return self._inner.data

    @property
    def y_parity(self) -> int:
        return self._inner.y_parity

    @property
    def r(self) -> int:
        return self._inner.r

    @property
    def s(self) -> int:
        return self._inner.s

    @property
    def access_list(self) -> Sequence[Tuple[Address, Sequence[int]]]:
        return self._inner.access_list

    def get_sender(self) -> Address:
        return self._inner.get_sender()

    def get_message_for_signing(self) -> bytes:
        return self._inner.get_message_for_signing()

    def check_signature_validity(self) -> None:
        self._inner.check_signature_validity()

    @cached_property
    def hash(self) -> Hash32:
        return cast(Hash32, keccak(self.encode()))

    def get_intrinsic_gas(self) -> int:
        return self._inner.get_intrinsic_gas()

    def copy(self, **overrides: Any) -> "TypedTransaction":
        inner_copy = self._inner.copy(**overrides)
        return type(self)(self.type_id, inner_copy)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, TypedTransaction):
            return False
        else:
            return self.type_id == other.type_id and self._inner == other._inner

    def make_receipt(
        self,
        status: bytes,
        gas_used: int,
        log_entries: Tuple[Tuple[bytes, Tuple[int, ...], bytes], ...],
    ) -> ReceiptAPI:
        inner_receipt = self._inner.make_receipt(status, gas_used, log_entries)

        return self.receipt_builder.typed_receipt_class(self.type_id, inner_receipt)

    def __hash__(self) -> int:
        return hash((self.type_id, self._inner))


class BerlinTransactionBuilder(TransactionBuilderAPI):
    """
    Responsible for serializing transactions of ambiguous type.

    It dispatches to either the legacy transaction type or the new typed
    transaction, depending on the nature of the encoded/decoded transaction.
    """

    legacy_signed = BerlinLegacyTransaction
    legacy_unsigned = BerlinUnsignedLegacyTransaction
    typed_transaction = TypedTransaction

    @classmethod
    def decode(cls, encoded: bytes) -> SignedTransactionAPI:
        if len(encoded) == 0:
            raise ValidationError(
                "Encoded transaction was empty, which makes it invalid"
            )

        type_id = to_int(encoded[0])
        if type_id in VALID_TRANSACTION_TYPES:
            return cls.typed_transaction.decode(encoded)
        else:
            return rlp.decode(encoded, sedes=cls.legacy_signed)

    @classmethod
    def deserialize(cls, encoded: DecodedZeroOrOneLayerRLP) -> SignedTransactionAPI:
        if isinstance(encoded, bytes):
            return cls.typed_transaction.deserialize(encoded)
        else:
            return cls.legacy_signed.deserialize(encoded)

    @classmethod
    def serialize(cls, obj: SignedTransactionAPI) -> DecodedZeroOrOneLayerRLP:
        if isinstance(obj, cls.typed_transaction):
            return cls.typed_transaction.serialize(obj)
        else:
            return cls.legacy_signed.serialize(obj)

    @classmethod
    def create_unsigned_transaction(
        cls,
        *,
        nonce: int,
        gas_price: int,
        gas: int,
        to: Address,
        value: int,
        data: bytes,
    ) -> UnsignedTransactionAPI:
        return cls.legacy_unsigned(nonce, gas_price, gas, to, value, data)

    @classmethod
    def new_transaction(
        cls,
        nonce: int,
        gas_price: int,
        gas: int,
        to: Address,
        value: int,
        data: bytes,
        v: int,
        r: int,
        s: int,
    ) -> SignedTransactionAPI:
        return cls.legacy_signed(nonce, gas_price, gas, to, value, data, v, r, s)

    @classmethod
    def new_unsigned_access_list_transaction(
        cls,
        chain_id: int,
        nonce: int,
        gas_price: int,
        gas: int,
        to: Address,
        value: int,
        data: bytes,
        access_list: Sequence[Tuple[Address, Sequence[int]]],
    ) -> TypedTransaction:
        transaction = UnsignedAccessListTransaction(
            chain_id,
            nonce,
            gas_price,
            gas,
            to,
            value,
            data,
            access_list,
        )
        return transaction

    @classmethod
    def new_access_list_transaction(
        cls,
        chain_id: int,
        nonce: int,
        gas_price: int,
        gas: int,
        to: Address,
        value: int,
        data: bytes,
        access_list: Sequence[Tuple[Address, Sequence[int]]],
        y_parity: int,
        r: int,
        s: int,
    ) -> TypedTransaction:
        transaction = AccessListTransaction(
            chain_id,
            nonce,
            gas_price,
            gas,
            to,
            value,
            data,
            access_list,
            y_parity,
            r,
            s,
        )
        return cls.typed_transaction(ACCESS_LIST_TRANSACTION_TYPE, transaction)


def _get_access_list_txn_intrinsic_gas(
    klass: Union[UnsignedAccessListTransaction, AccessListTransaction]
) -> int:
    core_gas = calculate_intrinsic_gas(ISTANBUL_TX_GAS_SCHEDULE, klass)

    num_addresses = len(klass.access_list)
    preload_address_costs = ACCESS_LIST_ADDRESS_COST_EIP_2930 * num_addresses

    num_slots = sum(len(slots) for _, slots in klass.access_list)
    preload_slot_costs = ACCESS_LIST_STORAGE_KEY_COST_EIP_2930 * num_slots

    return core_gas + preload_address_costs + preload_slot_costs
