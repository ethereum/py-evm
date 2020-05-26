from eth_keys.datatypes import PrivateKey
from eth_typing import Address

from eth.vm.forks.muir_glacier.transactions import (
    MuirGlacierTransaction,
    MuirGlacierUnsignedTransaction,
)

from eth._utils.transactions import (
    create_transaction_signature,
)


class BerlinTransaction(MuirGlacierTransaction):
    @classmethod
    def create_unsigned_transaction(cls,
                                    *,
                                    nonce: int,
                                    gas_price: int,
                                    gas: int,
                                    to: Address,
                                    value: int,
                                    data: bytes) -> 'BerlinUnsignedTransaction':
        return BerlinUnsignedTransaction(nonce, gas_price, gas, to, value, data)


class BerlinUnsignedTransaction(MuirGlacierUnsignedTransaction):
    def as_signed_transaction(self,
                              private_key: PrivateKey,
                              chain_id: int = None) -> BerlinTransaction:
        v, r, s = create_transaction_signature(self, private_key, chain_id=chain_id)
        return BerlinTransaction(
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
