from eth_keys.datatypes import PrivateKey
from eth_typing import Address

from eth.vm.forks.petersburg.transactions import (
    PetersburgTransaction,
    PetersburgUnsignedTransaction,
)

from eth._utils.transactions import (
    create_transaction_signature,
)


class IstanbulTransaction(PetersburgTransaction):
    @classmethod
    def create_unsigned_transaction(cls,
                                    *,
                                    nonce: int,
                                    gas_price: int,
                                    gas: int,
                                    to: Address,
                                    value: int,
                                    data: bytes) -> 'IstanbulUnsignedTransaction':
        return IstanbulUnsignedTransaction(nonce, gas_price, gas, to, value, data)


class IstanbulUnsignedTransaction(PetersburgUnsignedTransaction):
    def as_signed_transaction(self,
                              private_key: PrivateKey,
                              chain_id: int = None) -> IstanbulTransaction:
        v, r, s = create_transaction_signature(self, private_key, chain_id=chain_id)
        return IstanbulTransaction(
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
