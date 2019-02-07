import logging

from eth_utils.toolz import (
    curry,
)
from lahja import (
    BroadcastConfig,
    Endpoint,
)

from trinity.constants import (
    MAIN_EVENTBUS_ENDPOINT,
)
from trinity.events import (
    AvailableEndpointsUpdated,
    ShutdownRequest,
)


def request_shutdown(event_bus: Endpoint, reason: str) -> None:
    event_bus.broadcast(
        ShutdownRequest(reason),
        BroadcastConfig(filter_endpoint=MAIN_EVENTBUS_ENDPOINT)
    )


@curry
def connect_to_other_endpoints(logger: logging.Logger,
                               event_bus: Endpoint,
                               ev: AvailableEndpointsUpdated) -> None:

    for connection_config in ev.available_endpoints:
        if connection_config.name == event_bus.name:
            continue
        elif event_bus.is_connected_to(connection_config.name):
            continue
        else:
            logger.info(
                "EventBus Endpoint %s connecting to other Endpoint %s",
                event_bus.name,
                connection_config.name
            )
            event_bus.connect_to_endpoints_nowait(connection_config)
