from abc import (
    ABC,
    abstractmethod
)
import asyncio
import contextlib
from typing import (
    Iterator,
    Generic,
    TypeVar
)

_TMsg = TypeVar('_TMsg')


class MsgQueueExposer(ABC, Generic[_TMsg]):

    @abstractmethod
    def subscribe(self, subscriber: 'MsgQueueSubscriber[_TMsg]') -> None:
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def unsubscribe(self, subscriber: 'MsgQueueSubscriber[_TMsg]') -> None:
        raise NotImplementedError("Must be implemented by subclasses")


class MsgQueueSubscriber(Generic[_TMsg]):
    _msg_queue: 'asyncio.Queue[_TMsg]' = None

    @property
    def msg_queue(self) -> 'asyncio.Queue[_TMsg]':
        if self._msg_queue is None:
            self._msg_queue = asyncio.Queue(maxsize=10000)
        return self._msg_queue

    @contextlib.contextmanager
    def subscribe(
            self,
            msg_queue_exposer: MsgQueueExposer[_TMsg]) -> Iterator[None]:
        msg_queue_exposer.subscribe(self)
        try:
            yield
        finally:
            msg_queue_exposer.unsubscribe(self)
