from eth_keys.datatypes import (
    PrivateKey,
)
from eth_typing import (
    Address,
)

from eth._utils.transactions import (
    create_transaction_signature,
)
from eth.vm.forks.byzantium.transactions import (
    ByzantiumTransaction,
    ByzantiumUnsignedTransaction,
)


class ConstantinopleTransaction(ByzantiumTransaction):
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
    ) -> "ConstantinopleUnsignedTransaction":
        return ConstantinopleUnsignedTransaction(nonce, gas_price, gas, to, value, data)


class ConstantinopleUnsignedTransaction(ByzantiumUnsignedTransaction):
    def as_signed_transaction(
        self, private_key: PrivateKey, chain_id: int = None
    ) -> ConstantinopleTransaction:
        v, r, s = create_transaction_signature(self, private_key, chain_id=chain_id)
        return ConstantinopleTransaction(
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
