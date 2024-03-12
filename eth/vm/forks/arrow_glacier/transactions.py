from abc import (
    ABC,
)

from eth_keys.datatypes import (
    PrivateKey,
)

from eth._utils.transactions import (
    create_transaction_signature,
)
from eth.vm.forks.london.transactions import (
    LondonLegacyTransaction,
    LondonTransactionBuilder,
    LondonUnsignedLegacyTransaction,
)


class ArrowGlacierLegacyTransaction(LondonLegacyTransaction, ABC):
    pass


class ArrowGlacierUnsignedLegacyTransaction(LondonUnsignedLegacyTransaction):
    def as_signed_transaction(
        self, private_key: PrivateKey, chain_id: int = None
    ) -> ArrowGlacierLegacyTransaction:
        v, r, s = create_transaction_signature(self, private_key, chain_id=chain_id)
        return ArrowGlacierLegacyTransaction(
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


class ArrowGlacierTransactionBuilder(LondonTransactionBuilder):
    legacy_signed = ArrowGlacierLegacyTransaction
    legacy_unsigned = ArrowGlacierUnsignedLegacyTransaction
