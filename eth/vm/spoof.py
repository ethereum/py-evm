from typing import Any

from eth.rlp.transactions import BaseTransaction
from eth._utils.spoof import SpoofAttributes


class SpoofTransaction(SpoofAttributes):
    def __init__(self, transaction: BaseTransaction, **overrides: Any) -> None:
        super().__init__(transaction, **overrides)
