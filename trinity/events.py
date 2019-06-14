from dataclasses import dataclass
from typing import (
    Tuple,
)

from lahja import (
    BaseEvent,
    ConnectionConfig,
)


@dataclass
class ShutdownRequest(BaseEvent):

    reason: str = ""


@dataclass
class EventBusConnected(BaseEvent):
    """
    Broadcasted when a new :class:`~lahja.endpoint.Endpoint` connects to the ``main``
    :class:`~lahja.endpoint.Endpoint`. The :class:`~lahja.endpoint.Endpoint` that connects to the
    the ``main`` :class:`~lahja.endpoint.Endpoint` should send
    :class:`~trinity.events.EventBusConnected` to ``main`` which will then cause ``main`` to send
    a :class:`~trinity.events.AvailableEndpointsUpdated` event to every connected
    :class:`~lahja.endpoint.Endpoint`, making them aware of other endpoints they can connect to.
    """

    connection_config: ConnectionConfig


@dataclass
class AvailableEndpointsUpdated(BaseEvent):
    """
    Broadcasted by the ``main`` :class:`~lahja.endpoint.Endpoint` after it has received a
    :class:`~trinity.events.EventBusConnected` event. The ``available_endpoints`` property
    lists all available endpoints that are known at the time when the event is raised.
    """

    available_endpoints: Tuple[ConnectionConfig, ...]
