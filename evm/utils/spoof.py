from evm.constants import (
    DEFAULT_SPOOF_V,
    DEFAULT_SPOOF_R,
    DEFAULT_SPOOF_S,
)


from evm.rlp.transactions import (
    BaseTransaction,
    BaseUnsignedTransaction,
)
from typing import Callable, Union, Any

SPOOF_ATTRIBUTES_DEFAULTS = {
    'v': DEFAULT_SPOOF_V,
    'r': DEFAULT_SPOOF_R,
    's': DEFAULT_SPOOF_S
}


class SpoofAttributes:
    def __init__(
            self,
            spoof_target: Union[BaseTransaction, BaseUnsignedTransaction],
            **overrides: Any) -> None:
        self.spoof_target = spoof_target
        self.overrides = overrides

        if 'from_' in overrides:
            if hasattr(spoof_target, 'sender'):
                raise TypeError(
                    "A from_ parameter can only be supplied when the spoof target",
                    "does not have a sender attribute.  SpoofTransaction will not attempt",
                    "to override the sender of a signed transaction.")

            overrides['sender'] = overrides['from_']
            overrides['get_sender'] = lambda: overrides['from_']
            for attr, value in SPOOF_ATTRIBUTES_DEFAULTS.items():
                if not hasattr(spoof_target, attr):
                    overrides[attr] = value

    def __getattr__(self, attr: str) -> Union[int, Callable, bytes]:
        if attr in self.overrides:
            return self.overrides[attr]
        else:
            return getattr(self.spoof_target, attr)


class SpoofTransaction(SpoofAttributes):
    def __init__(self, transaction: BaseTransaction, **overrides: Any) -> None:
        super().__init__(transaction, **overrides)
