import rlp

from eth_keys.datatypes import PrivateKey

from eth_typing import (
    Address,
)

from eth.constants import (
    CREATE_CONTRACT_ADDRESS,
    GAS_TX,
    GAS_TXDATAZERO,
    GAS_TXDATANONZERO,
)
from eth.validation import (
    validate_uint256,
    validate_is_integer,
    validate_is_bytes,
    validate_lt_secpk1n,
    validate_lte,
    validate_gte,
    validate_canonical_address,
)

from eth.rlp.transactions import (
    BaseTransaction,
    BaseUnsignedTransaction,
)

from eth._utils.transactions import (
    create_transaction_signature,
    extract_transaction_sender,
    validate_transaction_signature,
)


class FrontierTransaction(BaseTransaction):

    @property
    def v_min(self) -> int:
        return 27

    @property
    def v_max(self) -> int:
        return 28

    def validate(self) -> None:
        validate_uint256(self.nonce, title="Transaction.nonce")
        validate_uint256(self.gas_price, title="Transaction.gas_price")
        validate_uint256(self.gas, title="Transaction.gas")
        if self.to != CREATE_CONTRACT_ADDRESS:
            validate_canonical_address(self.to, title="Transaction.to")
        validate_uint256(self.value, title="Transaction.value")
        validate_is_bytes(self.data, title="Transaction.data")

        validate_uint256(self.v, title="Transaction.v")
        validate_uint256(self.r, title="Transaction.r")
        validate_uint256(self.s, title="Transaction.s")

        validate_lt_secpk1n(self.r, title="Transaction.r")
        validate_gte(self.r, minimum=1, title="Transaction.r")
        validate_lt_secpk1n(self.s, title="Transaction.s")
        validate_gte(self.s, minimum=1, title="Transaction.s")

        validate_gte(self.v, minimum=self.v_min, title="Transaction.v")
        validate_lte(self.v, maximum=self.v_max, title="Transaction.v")

        super().validate()

    def check_signature_validity(self) -> None:
        validate_transaction_signature(self)

    def get_sender(self) -> Address:
        return extract_transaction_sender(self)

    def get_intrinsic_gas(self) -> int:
        return _get_frontier_intrinsic_gas(self.data)

    def get_message_for_signing(self) -> bytes:
        return rlp.encode(FrontierUnsignedTransaction(
            nonce=self.nonce,
            gas_price=self.gas_price,
            gas=self.gas,
            to=self.to,
            value=self.value,
            data=self.data,
        ))

    @classmethod
    def create_unsigned_transaction(cls,
                                    *,
                                    nonce: int,
                                    gas_price: int,
                                    gas: int,
                                    to: Address,
                                    value: int,
                                    data: bytes) -> 'FrontierUnsignedTransaction':
        return FrontierUnsignedTransaction(nonce, gas_price, gas, to, value, data)


class FrontierUnsignedTransaction(BaseUnsignedTransaction):

    def validate(self) -> None:
        validate_uint256(self.nonce, title="Transaction.nonce")
        validate_is_integer(self.gas_price, title="Transaction.gas_price")
        validate_uint256(self.gas, title="Transaction.gas")
        if self.to != CREATE_CONTRACT_ADDRESS:
            validate_canonical_address(self.to, title="Transaction.to")
        validate_uint256(self.value, title="Transaction.value")
        validate_is_bytes(self.data, title="Transaction.data")
        super().validate()

    def as_signed_transaction(self, private_key: PrivateKey) -> FrontierTransaction:
        v, r, s = create_transaction_signature(self, private_key)
        return FrontierTransaction(
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

    def get_intrinsic_gas(self) -> int:
        return _get_frontier_intrinsic_gas(self.data)


def _get_frontier_intrinsic_gas(transaction_data: bytes) -> int:
    num_zero_bytes = transaction_data.count(b'\x00')
    num_non_zero_bytes = len(transaction_data) - num_zero_bytes
    return (
        GAS_TX +
        num_zero_bytes * GAS_TXDATAZERO +
        num_non_zero_bytes * GAS_TXDATANONZERO
    )
