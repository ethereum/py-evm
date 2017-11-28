from evm.vm.forks.spurious_dragon.transactions import (
    SpuriousDragonTransaction,
    SpuriousDragonUnsignedTransaction,
)

from evm.utils.transactions import (
    create_transaction_signature,
)


class ByzantiumTransaction(SpuriousDragonTransaction):
    @classmethod
    def create_unsigned_transaction(cls, nonce, gas_price, gas, to, value, data):
        return ByzantiumUnsignedTransaction(nonce, gas_price, gas, to, value, data)


class ByzantiumUnsignedTransaction(SpuriousDragonUnsignedTransaction):
    def as_signed_transaction(self, private_key, chain_id=None):
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
