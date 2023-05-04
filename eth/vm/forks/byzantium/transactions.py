from eth_keys.datatypes import (
    PrivateKey,
)
from eth_typing import (
    Address,
)

from eth._utils.transactions import (
    create_transaction_signature,
)
from eth.vm.forks.spurious_dragon.transactions import (
    SpuriousDragonTransaction,
    SpuriousDragonUnsignedTransaction,
)


class ByzantiumTransaction(SpuriousDragonTransaction):
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
    ) -> "ByzantiumUnsignedTransaction":
        return ByzantiumUnsignedTransaction(nonce, gas_price, gas, to, value, data)


class ByzantiumUnsignedTransaction(SpuriousDragonUnsignedTransaction):
    def as_signed_transaction(
        self, private_key: PrivateKey, chain_id: int = None
    ) -> ByzantiumTransaction:
        v, r, s = create_transaction_signature(self, private_key, chain_id=chain_id)
        return ByzantiumTransaction(
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
