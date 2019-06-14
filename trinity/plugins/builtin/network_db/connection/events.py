from dataclasses import (
    dataclass,
)
from typing import Type

from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
)

from p2p.kademlia import Node


class BaseConnectionTrackerEvent(BaseEvent):
    pass


@dataclass
class BlacklistEvent(BaseConnectionTrackerEvent):

    remote: Node
    timeout_seconds: int
    reason: str


@dataclass
class ShouldConnectToPeerResponse(BaseConnectionTrackerEvent):

    should_connect: bool


@dataclass
class ShouldConnectToPeerRequest(BaseRequestResponseEvent[ShouldConnectToPeerResponse]):

    remote: Node

    @staticmethod
    def expected_response_type() -> Type[ShouldConnectToPeerResponse]:
        return ShouldConnectToPeerResponse
