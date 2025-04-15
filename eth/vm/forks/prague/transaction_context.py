from typing import (
    Sequence,
)

from eth.abc import (
    SetCodeAuthorizationAPI,
)
from eth.vm.forks.cancun.transaction_context import (
    CancunTransactionContext,
)


class PragueTransactionContext(CancunTransactionContext):
    @property
    def authorization_list(self) -> Sequence[SetCodeAuthorizationAPI]:
        return self._authorization_list
