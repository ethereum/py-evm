import rlp

from evm.constants import (
    GAS_TX,
    GAS_TXCREATE,
    GAS_TXDATAZERO,
    GAS_TXDATANONZERO,
    CREATE_CONTRACT_ADDRESS,
)
from evm.validation import (
    validate_lt_secpk1n2,
)

from evm.vm.forks.frontier.transactions import (
    FrontierTransaction,
    FrontierUnsignedTransaction,
)

from evm.utils.transactions import (
    create_transaction_signature,
)


class HomesteadTransaction(FrontierTransaction):
    def validate(self):
        super(HomesteadTransaction, self).validate()
        validate_lt_secpk1n2(self.s, title="Transaction.s")

    def get_intrinsic_gas(self):
        return _get_homestead_intrinsic_gas(self)

    def get_message_for_signing(self):
        return rlp.encode(HomesteadUnsignedTransaction(
            nonce=self.nonce,
            gas_price=self.gas_price,
            gas=self.gas,
            to=self.to,
            value=self.value,
            data=self.data,
        ))

    @classmethod
    def create_unsigned_transaction(cls, nonce, gas_price, gas, to, value, data):
        return HomesteadUnsignedTransaction(nonce, gas_price, gas, to, value, data)


class HomesteadUnsignedTransaction(FrontierUnsignedTransaction):
    def as_signed_transaction(self, private_key):
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


def _get_homestead_intrinsic_gas(transaction):
    num_zero_bytes = transaction.data.count(b'\x00')
    num_non_zero_bytes = len(transaction.data) - num_zero_bytes
    if transaction.to == CREATE_CONTRACT_ADDRESS:
        create_cost = GAS_TXCREATE
    else:
        create_cost = 0
    return (
        GAS_TX +
        num_zero_bytes * GAS_TXDATAZERO +
        num_non_zero_bytes * GAS_TXDATANONZERO +
        create_cost
    )
