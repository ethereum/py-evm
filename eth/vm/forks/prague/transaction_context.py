from typing import (
    Sequence,
)

from eth.typing import (
    Authorization,
)
from eth.vm.forks.cancun.transaction_context import (
    CancunTransactionContext,
)


class PragueTransactionContext(CancunTransactionContext):
    @property
    def authorization_list(self) -> Sequence[Authorization]:
        return self._authorization_list
