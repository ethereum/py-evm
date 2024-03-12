from functools import (
    partial,
)

from eth_keys.datatypes import (
    PrivateKey,
)
from eth_typing import (
    Address,
)
import rlp

from eth._utils.transactions import (
    IntrinsicGasSchedule,
    calculate_intrinsic_gas,
    create_transaction_signature,
)
from eth.constants import (
    GAS_TXCREATE,
)
from eth.validation import (
    validate_lt_secpk1n2,
)
from eth.vm.forks.frontier.transactions import (
    FRONTIER_TX_GAS_SCHEDULE,
    FrontierTransaction,
    FrontierUnsignedTransaction,
)

HOMESTEAD_TX_GAS_SCHEDULE: IntrinsicGasSchedule = FRONTIER_TX_GAS_SCHEDULE._replace(
    gas_txcreate=GAS_TXCREATE,
)


homestead_get_intrinsic_gas = partial(
    calculate_intrinsic_gas, HOMESTEAD_TX_GAS_SCHEDULE
)


class HomesteadTransaction(FrontierTransaction):
    def validate(self) -> None:
        super().validate()
        validate_lt_secpk1n2(self.s, title="Transaction.s")

    def get_intrinsic_gas(self) -> int:
        return homestead_get_intrinsic_gas(self)

    def get_message_for_signing(self) -> bytes:
        return rlp.encode(
            HomesteadUnsignedTransaction(
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
    ) -> "HomesteadUnsignedTransaction":
        return HomesteadUnsignedTransaction(nonce, gas_price, gas, to, value, data)


class HomesteadUnsignedTransaction(FrontierUnsignedTransaction):
    def as_signed_transaction(
        self,
        private_key: PrivateKey,
        chain_id: int = None,  # unused until SpuriousDragon
    ) -> HomesteadTransaction:
        v, r, s = create_transaction_signature(self, private_key)
        return HomesteadTransaction(
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
        return homestead_get_intrinsic_gas(self)
