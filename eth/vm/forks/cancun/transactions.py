from abc import (
    ABC,
)

from eth_keys.datatypes import (
    PrivateKey,
)

from eth._utils.transactions import (
    create_transaction_signature,
)
from eth.vm.forks.shanghai.transactions import (
    ShanghaiLegacyTransaction,
    ShanghaiTransactionBuilder,
    ShanghaiUnsignedLegacyTransaction,
)


class CancunLegacyTransaction(ShanghaiLegacyTransaction, ABC):
    pass


class CancunUnsignedLegacyTransaction(ShanghaiUnsignedLegacyTransaction):
    def as_signed_transaction(
        self, private_key: PrivateKey, chain_id: int = None
    ) -> CancunLegacyTransaction:
        v, r, s = create_transaction_signature(self, private_key, chain_id=chain_id)
        return CancunLegacyTransaction(
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


class CancunTransactionBuilder(ShanghaiTransactionBuilder):
    legacy_signed = CancunLegacyTransaction
    legacy_unsigned = CancunUnsignedLegacyTransaction
