from eth_keys.datatypes import PrivateKey
from eth_typing import Address
from eth_utils import (
    to_int,
)
from rlp.exceptions import (
    DeserializationError,
)

from eth.abc import (
    SignedTransactionAPI,
    TransactionBuilderAPI,
    UnsignedTransactionAPI,
)
from eth.exceptions import UnrecognizedTransactionType
from eth.vm.forks.muir_glacier.transactions import (
    MuirGlacierTransaction,
    MuirGlacierUnsignedTransaction,
)

from eth._utils.transactions import (
    create_transaction_signature,
)


class BerlinLegacyTransaction(MuirGlacierTransaction):
    pass


class BerlinUnsignedLegacyTransaction(MuirGlacierUnsignedTransaction):
    def as_signed_transaction(self,
                              private_key: PrivateKey,
                              chain_id: int = None) -> BerlinLegacyTransaction:
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


class BerlinTransactionBuilder(TransactionBuilderAPI):
    """
    Responsible for serializing transactions of ambiguous type.

    It dispatches to either the legacy transaction type or the new typed
    transaction, depending on the nature of the encoded/decoded transaction.
    """
    legacy_signed = BerlinLegacyTransaction
    legacy_unsigned = BerlinUnsignedLegacyTransaction

    @classmethod
    def deserialize(cls, encoded: bytes) -> SignedTransactionAPI:
        if len(encoded) == 0:
            raise DeserializationError(
                "Encoded transaction was empty, which makes it invalid",
                encoded,
            )

        if isinstance(encoded, bytes):
            transaction_type = to_int(encoded[0])
            if transaction_type == 1:
                raise UnrecognizedTransactionType(transaction_type, "TODO: Implement EIP-2930")
            elif transaction_type in range(0, 0x80):
                raise UnrecognizedTransactionType(transaction_type, "Unknown transaction type")
            else:
                raise DeserializationError(
                    f"Typed Transaction must start with 0-0x7f, but got {hex(transaction_type)}",
                    encoded,
                )
        else:
            return cls.legacy_signed.deserialize(encoded)

    @classmethod
    def serialize(cls, obj: SignedTransactionAPI) -> bytes:
        return cls.legacy_signed.serialize(obj)

    @classmethod
    def create_unsigned_transaction(cls,
                                    *,
                                    nonce: int,
                                    gas_price: int,
                                    gas: int,
                                    to: Address,
                                    value: int,
                                    data: bytes) -> UnsignedTransactionAPI:
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
            s: int) -> SignedTransactionAPI:
        return cls.legacy_signed(nonce, gas_price, gas, to, value, data, v, r, s)
