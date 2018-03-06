from evm.transaction_context import (
    BaseTransactionContext,
)
from evm.validation import (
    validate_sig_hash,
    validate_uint256,
    validate_canonical_address,
)


class ShardingTransactionContext(BaseTransactionContext):
    def __init__(self, origin, sig_hash, transaction_gas_limit):
        validate_canonical_address(origin, title="TransactionContext.origin")
        self._origin = origin
        validate_sig_hash(sig_hash, title="ShardingTransactionContext.sig_hash")
        self._sig_hash = sig_hash
        validate_uint256(
            transaction_gas_limit,
            title="ShardingTransactionContext.transaction_gas_limit",
        )
        self._transaction_gas_limit = transaction_gas_limit

    @property
    def sig_hash(self):
        return self._sig_hash

    @property
    def transaction_gas_limit(self):
        return self._transaction_gas_limit
