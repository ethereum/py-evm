from functools import (
    partial,
)
from typing import (
    Sequence,
    Tuple,
)

from eth_keys.datatypes import (
    PrivateKey,
)
from eth_typing import (
    Address,
    Hash32,
)
import rlp

from eth._utils.transactions import (
    V_OFFSET,
    IntrinsicGasSchedule,
    calculate_intrinsic_gas,
    create_transaction_signature,
    extract_transaction_sender,
    validate_transaction_signature,
)
from eth.abc import (
    ReceiptAPI,
    SignedTransactionAPI,
)
from eth.constants import (
    CREATE_CONTRACT_ADDRESS,
    GAS_TX,
    GAS_TXDATANONZERO,
    GAS_TXDATAZERO,
)
from eth.rlp.logs import (
    Log,
)
from eth.rlp.receipts import (
    Receipt,
)
from eth.rlp.transactions import (
    BaseTransaction,
    BaseUnsignedTransaction,
)
from eth.validation import (
    validate_canonical_address,
    validate_gte,
    validate_is_bytes,
    validate_is_integer,
    validate_lt_secpk1n,
    validate_lte,
    validate_uint64,
    validate_uint256,
)

FRONTIER_TX_GAS_SCHEDULE: IntrinsicGasSchedule = IntrinsicGasSchedule(
    gas_tx=GAS_TX,
    gas_txcreate=0,
    gas_txdatazero=GAS_TXDATAZERO,
    gas_txdatanonzero=GAS_TXDATANONZERO,
)


frontier_get_intrinsic_gas = partial(calculate_intrinsic_gas, FRONTIER_TX_GAS_SCHEDULE)


class FrontierTransaction(BaseTransaction):
    @property
    def y_parity(self) -> int:
        return self.v - V_OFFSET

    @property
    def v_min(self) -> int:
        return V_OFFSET

    @property
    def v_max(self) -> int:
        return V_OFFSET + 1

    def validate(self) -> None:
        validate_uint64(self.nonce, title="Transaction.nonce")
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
        return frontier_get_intrinsic_gas(self)

    def get_message_for_signing(self) -> bytes:
        return rlp.encode(
            FrontierUnsignedTransaction(
                nonce=self.nonce,
                gas_price=self.gas_price,
                gas=self.gas,
                to=self.to,
                value=self.value,
                data=self.data,
            )
        )

    @classmethod
    def create_unsigned_transaction(
        cls,
        *,
        nonce: int,
        gas_price: int,
        gas: int,
        to: Address,
        value: int,
        data: bytes
    ) -> "FrontierUnsignedTransaction":
        return FrontierUnsignedTransaction(nonce, gas_price, gas, to, value, data)

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
        return cls(nonce, gas_price, gas, to, value, data, v, r, s)

    def make_receipt(
        self,
        status: bytes,
        gas_used: int,
        log_entries: Tuple[Tuple[bytes, Tuple[int, ...], bytes], ...],
    ) -> ReceiptAPI:
        # 'status' is a misnomer in Frontier. Until Byzantium, it is the
        # intermediate state root.

        logs = [Log(address, topics, data) for address, topics, data in log_entries]

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

    @property
    def max_fee_per_blob_gas(self) -> int:
        raise NotImplementedError(
            "max_fee_per_blob_gas is not implemented until Cancun."
        )

    @property
    def blob_versioned_hashes(self) -> Sequence[Hash32]:
        raise NotImplementedError(
            "blob_versioned_hashes is not implemented until Cancun."
        )


class FrontierUnsignedTransaction(BaseUnsignedTransaction):
    def validate(self) -> None:
        validate_uint64(self.nonce, title="Transaction.nonce")
        validate_is_integer(self.gas_price, title="Transaction.gas_price")
        validate_uint256(self.gas, title="Transaction.gas")
        if self.to != CREATE_CONTRACT_ADDRESS:
            validate_canonical_address(self.to, title="Transaction.to")
        validate_uint256(self.value, title="Transaction.value")
        validate_is_bytes(self.data, title="Transaction.data")
        super().validate()

    def as_signed_transaction(
        self,
        private_key: PrivateKey,
        chain_id: int = None,  # unused until SpuriousDragon
    ) -> FrontierTransaction:
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
        return frontier_get_intrinsic_gas(self)

    # Old transactions are treated as setting both max-fees as the gas price
    @property
    def max_priority_fee_per_gas(self) -> int:
        return self.gas_price

    @property
    def max_fee_per_gas(self) -> int:
        return self.gas_price
