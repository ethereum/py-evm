from abc import (
    ABC,
)

from eth_keys.datatypes import (
    PrivateKey,
)

from eth._utils.transactions import (
    create_transaction_signature,
)
from eth.vm.forks.arrow_glacier.transactions import (
    ArrowGlacierLegacyTransaction,
    ArrowGlacierTransactionBuilder,
    ArrowGlacierUnsignedLegacyTransaction,
)


class GrayGlacierLegacyTransaction(ArrowGlacierLegacyTransaction, ABC):
    pass


class GrayGlacierUnsignedLegacyTransaction(ArrowGlacierUnsignedLegacyTransaction):
    def as_signed_transaction(
        self, private_key: PrivateKey, chain_id: int = None
    ) -> GrayGlacierLegacyTransaction:
        v, r, s = create_transaction_signature(self, private_key, chain_id=chain_id)
        return GrayGlacierLegacyTransaction(
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


class GrayGlacierTransactionBuilder(ArrowGlacierTransactionBuilder):
    legacy_signed = GrayGlacierLegacyTransaction
    legacy_unsigned = GrayGlacierUnsignedLegacyTransaction
