from typing import (
    Any,
    Callable,
    Type,
)
from types import TracebackType

from p2p.abc import HandlerSubscriptionAPI


class HandlerSubscription(HandlerSubscriptionAPI):
    def __init__(self, remove_fn: Callable[[], Any]) -> None:
        self._remove_fn = remove_fn

    def cancel(self) -> None:
        self._remove_fn()

    def __enter__(self) -> HandlerSubscriptionAPI:
        return self

    def __exit__(self,
                 exc_type: Type[BaseException],
                 exc_value: BaseException,
                 exc_tb: TracebackType) -> None:
        self._remove_fn()
