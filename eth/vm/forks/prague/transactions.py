from abc import (
    ABC,
)
from typing import (
    Dict,
    Sequence,
    Tuple,
    Type,
    TypedDict,
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
    ValidationError,
    to_bytes,
)
import rlp
from rlp.sedes import (
    CountableList,
    big_endian_int,
    binary,
)

from eth._utils.transactions import (
    create_transaction_signature,
    extract_transaction_sender,
    validate_transaction_signature,
)
from eth.abc import (
    ComputationAPI,
    ReceiptAPI,
    SetCodeAuthorizationAPI,
    SignedTransactionAPI,
    TransactionDecoderAPI,
    UnsignedTransactionAPI,
)
from eth.constants import (
    UINT_64_MAX,
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
    validate_chain_id_is_current_or_zero,
    validate_is_list_like,
    validate_lt_secpk1n2,
    validate_uint8,
    validate_uint64,
    validate_uint256,
)
from eth.vm.forks.berlin.constants import (
    ACCESS_LIST_TRANSACTION_TYPE,
)
from eth.vm.forks.berlin.transactions import (
    AccessListPayloadDecoder,
    AccountAccesses,
    TypedTransaction,
    calculate_txn_intrinsic_gas_berlin,
)
from eth.vm.forks.cancun.constants import (
    BLOB_TX_TYPE,
)
from eth.vm.forks.cancun.transactions import (
    BlobPayloadDecoder,
    CancunLegacyTransaction,
    CancunTransactionBuilder,
    CancunUnsignedLegacyTransaction,
)
from eth.vm.forks.london.constants import (
    DYNAMIC_FEE_TRANSACTION_TYPE,
)
from eth.vm.forks.london.transactions import (
    DynamicFeePayloadDecoder,
    DynamicFeeTransaction,
    UnsignedDynamicFeeTransaction,
)

from .constants import (
    PER_EMPTY_ACCOUNT_BASE_COST,
    SET_CODE_TRANSACTION_TYPE,
)
from .receipts import (
    PragueReceiptBuilder,
)


class PragueLegacyTransaction(CancunLegacyTransaction, ABC):
    pass


class PragueUnsignedLegacyTransaction(CancunUnsignedLegacyTransaction):
    def as_signed_transaction(
        self, private_key: PrivateKey, chain_id: int = None
    ) -> PragueLegacyTransaction:
        v, r, s = create_transaction_signature(self, private_key, chain_id=chain_id)
        return PragueLegacyTransaction(
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


class Authorization(rlp.Serializable, SetCodeAuthorizationAPI):
    chain_id: int
    address: Address
    nonce: int
    y_parity: int
    r: int
    s: int

    fields = (
        ("chain_id", big_endian_int),
        ("address", address),
        ("nonce", big_endian_int),
        ("y_parity", big_endian_int),
        ("r", big_endian_int),
        ("s", big_endian_int),
    )

    def validate_for_transaction(self) -> None:
        validate_uint256(self.chain_id)
        validate_uint64(self.nonce)
        validate_canonical_address(self.address)
        validate_uint8(self.y_parity)
        validate_uint256(self.r)
        validate_uint256(self.s)

    def validate(self, chain_id: int) -> None:
        validate_chain_id_is_current_or_zero(self.chain_id, chain_id)
        if self.nonce >= UINT_64_MAX:
            raise ValidationError(
                f"Nonce must be less than 2**64 - 1, got {self.nonce}"
            )
        validate_lt_secpk1n2(self.s)


class SetCodeTransaction(
    rlp.Serializable, SignedTransactionMethods, SignedTransactionAPI
):
    _type_id = SET_CODE_TRANSACTION_TYPE
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
        ("authorization_list", CountableList(Authorization)),
        ("y_parity", big_endian_int),
        ("r", big_endian_int),
        ("s", big_endian_int),
    ]

    def validate(self) -> None:
        # validate dynamic fee transaction fields
        DynamicFeeTransaction(
            self.chain_id,
            self.nonce,
            self.max_priority_fee_per_gas,
            self.max_fee_per_gas,
            self.gas,
            self.to,
            self.value,
            self.data,
            self.access_list,
            self.y_parity,
            self.r,
            self.s,
        ).validate()
        validate_canonical_address(self.to, title="Transaction.to")
        validate_is_list_like(
            self.authorization_list,
            title="Transaction.authorization_list",
            raise_if_empty=True,
        )
        for auth in self.authorization_list:
            auth.validate_for_transaction()

    @property
    def gas_price(self) -> None:
        raise AttributeError(
            "Gas price is no longer available."
            "See max_priority_fee_per_gas or max_fee_per_gas"
        )

    def get_sender(self) -> Address:
        return extract_transaction_sender(self)

    def get_message_for_signing(self) -> bytes:
        unsigned = UnsignedSetCodeTransaction(
            self.chain_id,
            self.nonce,
            self.max_priority_fee_per_gas,
            self.max_fee_per_gas,
            self.gas,
            self.to,
            self.value,
            self.data,
            self.access_list,
            self.authorization_list,
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
        return calculate_txn_intrinsic_gas_berlin(
            self
        ) + PER_EMPTY_ACCOUNT_BASE_COST * len(self.authorization_list)

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

    @property
    def max_fee_per_blob_gas(self) -> int:
        raise NotImplementedError(
            "max_fee_per_blob_gas is not a property of this transaction type."
        )

    @property
    def blob_versioned_hashes(self) -> Sequence[Hash32]:
        raise NotImplementedError(
            "blob_versioned_hashes is not a property of this transaction type."
        )


class UnsignedSetCodeTransaction(rlp.Serializable, UnsignedTransactionAPI):
    _type_id = SET_CODE_TRANSACTION_TYPE

    chain_id: int
    max_fee_per_gas: int
    max_priority_fee_per_gas: int
    access_list: Sequence[Tuple[Address, Sequence[int]]]
    authorization_list: Sequence[Authorization]

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
        ("authorization_list", CountableList(Authorization)),
    ]

    def as_signed_transaction(
        self, private_key: PrivateKey, chain_id: int = None
    ) -> "TypedTransaction":
        # validate and get message for signing
        message = self.get_message_for_signing()
        signature = private_key.sign_msg(message)
        y_parity, r, s = signature.vrs

        signed_transaction = SetCodeTransaction(
            self.chain_id,
            self.nonce,
            self.max_priority_fee_per_gas,
            self.max_fee_per_gas,
            self.gas,
            self.to,
            self.value,
            self.data,
            self.access_list,
            self.authorization_list,
            y_parity,
            r,
            s,
        )
        return PragueTypedTransaction(self._type_id, signed_transaction)

    def validate(self) -> None:
        UnsignedDynamicFeeTransaction(
            self.chain_id,
            self.nonce,
            self.max_priority_fee_per_gas,
            self.max_fee_per_gas,
            self.gas,
            self.to,
            self.value,
            self.data,
            self.access_list,
        ).validate()
        validate_is_list_like(
            self.authorization_list,
            title="Transaction.authorization_list",
            raise_if_empty=True,
        )
        for auth in self.authorization_list:
            auth.validate_for_transaction()

    @cached_property
    def _type_byte(self) -> bytes:
        return to_bytes(self._type_id)

    def get_message_for_signing(self) -> bytes:
        payload = rlp.encode(self)
        return self._type_byte + payload

    def gas_used_by(self, computation: ComputationAPI) -> int:
        return self.intrinsic_gas + computation.get_gas_used()

    def get_intrinsic_gas(self) -> int:
        berlin_gas = calculate_txn_intrinsic_gas_berlin(self)
        authorization_list_gas = PER_EMPTY_ACCOUNT_BASE_COST * len(
            self.authorization_list
        )
        return berlin_gas + authorization_list_gas

    @property
    def intrinsic_gas(self) -> int:
        return self.get_intrinsic_gas()


class SetCodePayloadDecoder(TransactionDecoderAPI):
    @classmethod
    def decode(cls, payload: bytes) -> SignedTransactionAPI:
        return rlp.decode(payload, sedes=SetCodeTransaction)


class PragueTypedTransaction(TypedTransaction):
    decoders: Dict[int, Type[TransactionDecoderAPI]] = {
        ACCESS_LIST_TRANSACTION_TYPE: AccessListPayloadDecoder,
        DYNAMIC_FEE_TRANSACTION_TYPE: DynamicFeePayloadDecoder,
        BLOB_TX_TYPE: BlobPayloadDecoder,
        SET_CODE_TRANSACTION_TYPE: SetCodePayloadDecoder,
    }
    receipt_builder = PragueReceiptBuilder

    @property
    def max_fee_per_blob_gas(self) -> int:
        return self._inner.max_fee_per_blob_gas

    @property
    def blob_versioned_hashes(self) -> Sequence[Hash32]:
        return self._inner.blob_versioned_hashes


class AuthorizationDict(TypedDict):
    chain_id: int
    address: Address
    nonce: int
    y_parity: int
    r: int
    s: int


class PragueTransactionBuilder(CancunTransactionBuilder):
    legacy_signed = PragueLegacyTransaction
    legacy_unsigned = PragueUnsignedLegacyTransaction
    typed_transaction: Type[TypedTransaction] = PragueTypedTransaction

    @classmethod
    def new_unsigned_set_code_transaction(
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
        authorization_list: Sequence[Union[Authorization, AuthorizationDict]],
    ) -> UnsignedSetCodeTransaction:
        return UnsignedSetCodeTransaction(
            chain_id=chain_id,
            nonce=nonce,
            gas=gas,
            max_priority_fee_per_gas=max_priority_fee_per_gas,
            max_fee_per_gas=max_fee_per_gas,
            to=to,
            value=value,
            data=data,
            access_list=access_list,
            authorization_list=[
                Authorization(**auth) if isinstance(auth, dict) else auth
                for auth in authorization_list
            ],
        )

    @classmethod
    def new_set_code_transaction(
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
        authorization_list: Sequence[Union[AuthorizationDict, Authorization]],
        y_parity: int,
        r: int,
        s: int,
    ) -> PragueTypedTransaction:
        transaction = SetCodeTransaction(
            chain_id=chain_id,
            nonce=nonce,
            max_priority_fee_per_gas=max_priority_fee_per_gas,
            max_fee_per_gas=max_fee_per_gas,
            gas=gas,
            to=to,
            value=value,
            data=data,
            access_list=access_list,
            authorization_list=[
                Authorization(**auth) if isinstance(auth, dict) else auth
                for auth in authorization_list
            ],
            y_parity=y_parity,
            r=r,
            s=s,
        )
        return PragueTypedTransaction(SET_CODE_TRANSACTION_TYPE, transaction)
