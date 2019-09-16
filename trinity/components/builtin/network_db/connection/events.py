from dataclasses import (
    dataclass,
)
from typing import Type

from lahja import (
    BaseEvent,
    BaseRequestResponseEvent,
)

from p2p.abc import NodeAPI


class BaseConnectionTrackerEvent(BaseEvent):
    pass


@dataclass
class BlacklistEvent(BaseConnectionTrackerEvent):

    remote: NodeAPI
    timeout_seconds: int
    reason: str


@dataclass
class ShouldConnectToPeerResponse(BaseConnectionTrackerEvent):

    should_connect: bool


@dataclass
class ShouldConnectToPeerRequest(BaseRequestResponseEvent[ShouldConnectToPeerResponse]):

    remote: NodeAPI

    @staticmethod
    def expected_response_type() -> Type[ShouldConnectToPeerResponse]:
        return ShouldConnectToPeerResponse
