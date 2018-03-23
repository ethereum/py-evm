from evm.rlp.transactions import BaseTransaction

from typing import Callable, Union, Any


class SpoofAttributes:
    def __init__(self, spoof_target: BaseTransaction, **overrides: Any) -> None:
        self.spoof_target = spoof_target
        self.overrides = overrides

    def __getattr__(self, attr: str) -> Union[int, Callable, bytes]:
        if attr in self.overrides:
            return self.overrides[attr]
        else:
            return getattr(self.spoof_target, attr)


class SpoofTransaction(SpoofAttributes):
    def __init__(self, transaction: BaseTransaction, **overrides: Any) -> None:
        super().__init__(transaction, **overrides)
