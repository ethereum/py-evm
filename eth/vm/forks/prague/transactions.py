from abc import (
    ABC,
)
from typing import (
    Tuple,
    Type,
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
    create_transaction_signature,
    extract_transaction_sender,
    validate_transaction_signature,
)
from eth.abc import (
    ReceiptAPI,
    SignedTransactionAPI,
    UnsignedTransactionAPI,
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
    validate_is_list_like,
    validate_is_transaction_access_list,
    validate_uint64,
    validate_uint256,
)
from eth.vm.forks.berlin.transactions import (
    AccountAccesses,
    TypedTransaction,
    _calculate_txn_intrinsic_gas_berlin,
)
from eth.vm.forks.cancun.transactions import (
    CancunLegacyTransaction,
    CancunTransactionBuilder,
    CancunUnsignedLegacyTransaction,
    UnsignedBlobTransaction,
)

from .constants import (
    SET_CODE_TRANSACTION_TYPE,
)


class PragueLegacyTransaction(CancunLegacyTransaction, ABC):
    pass


class Authorization(rlp.Serializable):
    fields = (
        ("chain_id", big_endian_int),
        ("account", address),
        ("nonce", big_endian_int),
        ("y_parity", big_endian_int),
        ("r", big_endian_int),
        ("s", big_endian_int),
    )


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
        ("destination", address),
        ("value", big_endian_int),
        ("data", binary),
        ("access_list", CountableList(AccountAccesses)),
        ("authorization_list", CountableList(Authorization)),
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
        unsigned = UnsignedBlobTransaction(
            self.chain_id,
            self.nonce,
            self.max_priority_fee_per_gas,
            self.max_fee_per_gas,
            self.gas,
            self.destination,
            self.value,
            self.data,
            self.access_list,
            self.max_fee_per_blob_gas,
            self.blob_versioned_hashes,
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
        # unchanged from Berlin
        return _calculate_txn_intrinsic_gas_berlin(self)

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
            # is this right: state_root=status?
            state_root=status,
            gas_used=gas_used,
            logs=logs,
        )


class PragueUnsignedLegacyTransaction(CancunUnsignedLegacyTransaction):
    def as_signed_transaction(
        self, private_key: PrivateKey, chain_id: int = None
    ) -> PragueLegacyTransaction:
        v, r, s = create_transaction_signature(self, private_key, chain_id=chain_id)
        return PragueLegacyTransaction(
            nonce=self.nonce,
            gas_price=self.gas_price,
            gas=self.gas,
            destination=self.destination,
            value=self.value,
            data=self.data,
            v=v,
            r=r,
            s=s,
        )

    def validate(self) -> None:
        # Validations
        # - [ ] len(authorization_list) > 0
        # - [ ] assert auth.chain_id < 2**64
        # - [ ] assert auth.nonce < 2**64
        # - [ ] assert len(auth.address) == 20
        # - [ ] assert auth.y_parity < 2**8
        # - [ ] assert auth.r < 2**256
        # - [ ] assert auth.s < 2**256

        # there are other validations from Cancun, should we add those too?
        validate_uint64(self.chain_id, title="Transaction.chain_id")
        validate_uint64(self.nonce, title="Transaction.nonce")
        validate_canonical_address(self.destination, title="Transaction.destination")
        # this y_parity value should actually be uint8, but we don't have one of those
        validate_uint64(self.y_parity, title="Transaction.nonce")
        validate_uint256(self.r, title="Transaction.nonce")
        validate_uint256(self.s, title="Transaction.nonce")
        validate_is_transaction_access_list(self.access_list)
        validate_is_list_like(
            self.authorization_list, title="Transaction.authorization_list"
        )
        for auth in self.authorization_list:
            # TODO - validate chain id is either 0 or current chain id
            # is Authorization.nonce the right title?
            validate_uint64(auth.nonce, title="Authorization.nonce")


class UnsignedSetCodeTransaction(
    rlp.Serializable, SignedTransactionMethods, UnsignedTransactionAPI
):
    _type_id = SET_CODE_TRANSACTION_TYPE

    chain_id: int

    fields = [
        ("chain_id", big_endian_int),
        ("nonce", big_endian_int),
        ("max_priority_fee_per_gas", big_endian_int),
        ("max_fee_per_gas", big_endian_int),
        ("gas", big_endian_int),
        ("destination", address),
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
            self.destination,
            self.value,
            self.data,
            self.access_list,
            self.authorization_list,
            y_parity,
            r,
            s,
        )
        return PragueTypedTransaction(self._type_id, signed_transaction)


class PragueTypedTransaction(TypedTransaction):
    pass


class PragueTransactionBuilder(CancunTransactionBuilder):
    legacy_signed = PragueLegacyTransaction
    legacy_unsigned = PragueUnsignedLegacyTransaction
    typed_transaction: Type[TypedTransaction] = PragueTypedTransaction
