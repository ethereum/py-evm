from typing import (
    Any,
    Union,
)

from eth._utils.spoof import (
    SpoofAttributes,
)
from eth.abc import (
    SignedTransactionAPI,
    UnsignedTransactionAPI,
)


class SpoofTransaction(SpoofAttributes):
    def __init__(
        self,
        transaction: Union[SignedTransactionAPI, UnsignedTransactionAPI],
        **overrides: Any
    ) -> None:
        super().__init__(transaction, **overrides)
