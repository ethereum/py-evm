from abc import (
    ABC,
)

from eth_keys.datatypes import (
    PrivateKey,
)

from eth._utils.transactions import (
    create_transaction_signature,
)
from eth.vm.forks.gray_glacier.transactions import (
    GrayGlacierLegacyTransaction,
    GrayGlacierTransactionBuilder,
    GrayGlacierUnsignedLegacyTransaction,
)


class ParisLegacyTransaction(GrayGlacierLegacyTransaction, ABC):
    pass


class ParisUnsignedLegacyTransaction(GrayGlacierUnsignedLegacyTransaction):
    def as_signed_transaction(
        self, private_key: PrivateKey, chain_id: int = None
    ) -> ParisLegacyTransaction:
        v, r, s = create_transaction_signature(self, private_key, chain_id=chain_id)
        return ParisLegacyTransaction(
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


class ParisTransactionBuilder(GrayGlacierTransactionBuilder):
    legacy_signed = ParisLegacyTransaction
    legacy_unsigned = ParisUnsignedLegacyTransaction
