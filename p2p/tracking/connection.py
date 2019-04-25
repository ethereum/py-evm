from abc import ABC, abstractmethod
import logging
from typing import (
    Dict,
    Type,
)

from p2p.kademlia import Node
from p2p.exceptions import (
    BaseP2PError,
    HandshakeFailure,
    TooManyPeersFailure,
)


FAILURE_TIMEOUTS: Dict[Type[Exception], int] = {}


def register_error(exception: Type[BaseP2PError], timeout_seconds: int) -> None:
    if exception in FAILURE_TIMEOUTS:
        raise KeyError(f"Exception class already registered")
    FAILURE_TIMEOUTS[exception] = timeout_seconds


register_error(HandshakeFailure, 10)  # 10 seconds
register_error(TooManyPeersFailure, 60)  # one minute


def get_timeout_for_failure(failure: BaseP2PError) -> int:
    for cls in type(failure).__mro__:
        if cls in FAILURE_TIMEOUTS:
            return FAILURE_TIMEOUTS[cls]
    failure_name = type(failure).__name__
    raise Exception(f'Unknown failure type: {failure_name}')


class BaseConnectionTracker(ABC):
    """
    Base API which defines the interface that the peer pool uses to record
    information about connection failures when attempting to connect to peers
    """
    logger = logging.getLogger('p2p.tracking.connection.ConnectionTracker')

    async def record_failure(self, remote: Node, failure: BaseP2PError) -> None:
        timeout_seconds = get_timeout_for_failure(failure)
        failure_name = type(failure).__name__

        return await self.record_blacklist(remote, timeout_seconds, failure_name)

    @abstractmethod
    async def record_blacklist(self, remote: Node, timeout_seconds: int, reason: str) -> None:
        pass

    @abstractmethod
    async def should_connect_to(self, remote: Node) -> bool:
        pass


class NoopConnectionTracker(BaseConnectionTracker):
    async def record_blacklist(self, remote: Node, timeout_seconds: int, reason: str) -> None:
        pass

    async def should_connect_to(self, remote: Node) -> bool:
        return True
