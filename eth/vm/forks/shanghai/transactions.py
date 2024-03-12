from abc import (
    ABC,
)

from eth_keys.datatypes import (
    PrivateKey,
)

from eth._utils.transactions import (
    create_transaction_signature,
)
from eth.vm.forks.paris.transactions import (
    ParisLegacyTransaction,
    ParisTransactionBuilder,
    ParisUnsignedLegacyTransaction,
)


class ShanghaiLegacyTransaction(ParisLegacyTransaction, ABC):
    pass


class ShanghaiUnsignedLegacyTransaction(ParisUnsignedLegacyTransaction):
    def as_signed_transaction(
        self, private_key: PrivateKey, chain_id: int = None
    ) -> ShanghaiLegacyTransaction:
        v, r, s = create_transaction_signature(self, private_key, chain_id=chain_id)
        return ShanghaiLegacyTransaction(
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


class ShanghaiTransactionBuilder(ParisTransactionBuilder):
    legacy_signed = ShanghaiLegacyTransaction
    legacy_unsigned = ShanghaiUnsignedLegacyTransaction
