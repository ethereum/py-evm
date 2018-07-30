from eth.vm.forks.byzantium.transactions import (
    ByzantiumTransaction,
    ByzantiumUnsignedTransaction,
)

from eth.utils.transactions import (
    create_transaction_signature,
)


class ConstantinopleTransaction(ByzantiumTransaction):
    @classmethod
    def create_unsigned_transaction(cls, nonce, gas_price, gas, to, value, data):
        return ConstantinopleUnsignedTransaction(nonce, gas_price, gas, to, value, data)


class ConstantinopleUnsignedTransaction(ByzantiumUnsignedTransaction):
    def as_signed_transaction(self, private_key, chain_id=None):
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
