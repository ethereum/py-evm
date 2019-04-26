from typing import Type

from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
)

from p2p.kademlia import Node


class BaseConnectionTrackerEvent(BaseEvent):
    pass


class BlacklistEvent(BaseConnectionTrackerEvent):
    def __init__(self, remote: Node, timeout_seconds: int, reason: str) -> None:
        self.remote = remote
        self.timeout_seconds = timeout_seconds
        self.reason = reason


class ShouldConnectToPeerResponse(BaseConnectionTrackerEvent):
    def __init__(self, should_connect: bool) -> None:
        self.should_connect = should_connect


class ShouldConnectToPeerRequest(BaseRequestResponseEvent[ShouldConnectToPeerResponse]):
    def __init__(self, remote: Node) -> None:
        self.remote = remote

    @staticmethod
    def expected_response_type() -> Type[ShouldConnectToPeerResponse]:
        return ShouldConnectToPeerResponse
