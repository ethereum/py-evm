import asyncio
from typing import (
    Tuple,
)

from lahja import (
    BroadcastConfig,
    ConnectionConfig,
    AsyncioEndpoint,
)

from trinity.constants import (
    MAIN_EVENTBUS_ENDPOINT,
)
from trinity.events import (
    AvailableEndpointsUpdated,
    EventBusConnected,
    ShutdownRequest,
)


class TrinityEventBusEndpoint(AsyncioEndpoint):
    """
    Lahja Endpoint with some Trinity specific logic.
    """

    def request_shutdown(self, reason: str) -> None:
        """
        Perfom a graceful shutdown of Trinity. Can be called from any process.
        """
        self.broadcast_nowait(
            ShutdownRequest(reason),
            BroadcastConfig(filter_endpoint=MAIN_EVENTBUS_ENDPOINT)
        )

    async def connect_to_other_endpoints(self,
                                         ev: AvailableEndpointsUpdated) -> None:

        # We only connect to Endpoints that appear after our own Endpoint in the set.
        # This ensures that we don't try to connect to an Endpoint while that remote
        # Endpoint also wants to connect to us.
        endpoints_to_connect_to = (
            connection_config
            for index, val in enumerate(ev.available_endpoints)
            if val.name == self.name
            for connection_config in ev.available_endpoints[index:]
            if not self.is_connected_to(connection_config.name)
        )

        for connection_config in endpoints_to_connect_to:

            self.logger.info(
                "EventBus Endpoint %s connecting to other Endpoint %s",
                self.name,
                connection_config.name
            )
            await self.connect_to_endpoints(connection_config)

    async def auto_connect_new_announced_endpoints(self) -> None:
        """
        Connect this endpoint to all new endpoints that are announced
        """
        async for event in self.stream(AvailableEndpointsUpdated):
            await self.connect_to_other_endpoints(event)

    async def announce_endpoint(self) -> None:
        """
        Announce this endpoint to the :class:`~trinity.endpoint.TrinityMainEventBusEndpoint` so
        that it will be further propagated to all other endpoints, allowing them to connect to us.
        """
        await self.wait_until_any_endpoint_subscribed_to(EventBusConnected)
        await self.broadcast(
            EventBusConnected(ConnectionConfig(name=self.name, path=self.ipc_path)),
            BroadcastConfig(filter_endpoint=MAIN_EVENTBUS_ENDPOINT)
        )


class TrinityMainEventBusEndpoint(TrinityEventBusEndpoint):
    """
    Endpoint that operates like a bootnode in the sense that every other endpoint is aware of this
    endpoint, connects to it by default and uses it to advertise itself to other endpoints.
    """

    available_endpoints: Tuple[ConnectionConfig, ...]

    def track_and_propagate_available_endpoints(self) -> None:
        """
        Track new announced endpoints and propagate them across all other existing endpoints.
        """
        self.available_endpoints = tuple()

        async def handle_new_endpoints(ev: EventBusConnected) -> None:
            self.available_endpoints = self.available_endpoints + (ev.connection_config,)
            self.logger.debug("New EventBus Endpoint connected %s", ev.connection_config.name)
            # Broadcast available endpoints to all connected endpoints, giving them
            # a chance to cross connect
            await self.wait_until_all_endpoints_subscribed_to(
                AvailableEndpointsUpdated,
                include_self=False
            )
            await self.broadcast(AvailableEndpointsUpdated(self.available_endpoints))
            self.logger.debug("Connected EventBus Endpoints %s", self.available_endpoints)

        def spawn_handle_new_endpoints(ev: EventBusConnected) -> None:
            asyncio.ensure_future(handle_new_endpoints(ev))

        self.subscribe(EventBusConnected, spawn_handle_new_endpoints)
