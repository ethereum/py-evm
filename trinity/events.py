from lahja import (
    BaseEvent,
    BroadcastConfig,
    Endpoint
)

from trinity.constants import (
    MAIN_EVENTBUS_ENDPOINT,
)


def request_shutdown(event_bus: Endpoint, reason: str) -> None:
    event_bus.broadcast(
        ShutdownRequest(reason),
        BroadcastConfig(filter_endpoint=MAIN_EVENTBUS_ENDPOINT)
    )


class ShutdownRequest(BaseEvent):

    def __init__(self, reason: str="") -> None:
        self.reason = reason
