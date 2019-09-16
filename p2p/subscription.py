from typing import (
    Any,
    Callable,
    Type,
)
from types import TracebackType

from p2p.abc import SubscriptionAPI


class Subscription(SubscriptionAPI):
    def __init__(self, cancel_fn: Callable[[], Any]) -> None:
        self._cancel_fn = cancel_fn

    def cancel(self) -> None:
        self._cancel_fn()

    def __enter__(self) -> SubscriptionAPI:
        return self

    def __exit__(self,
                 exc_type: Type[BaseException],
                 exc_value: BaseException,
                 exc_tb: TracebackType) -> None:
        self._cancel_fn()
