from typing import (
    Sequence,
)

from eth_typing import (
    Hash32,
)

from eth.vm.transaction_context import (
    BaseTransactionContext,
)


class CancunTransactionContext(BaseTransactionContext):
    @property
    def blob_versioned_hashes(self) -> Sequence[Hash32]:
        return self._blob_versioned_hashes
