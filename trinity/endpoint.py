import asyncio
from typing import (
    Tuple,
)
from lahja import (
    BroadcastConfig,
    ConnectionConfig,
    Endpoint,
)

from trinity.constants import (
    MAIN_EVENTBUS_ENDPOINT,
)
from trinity.events import (
    AvailableEndpointsUpdated,
    EventBusConnected,
    ShutdownRequest,
)


class TrinityEventBusEndpoint(Endpoint):
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

    def connect_to_other_endpoints(self,
                                   ev: AvailableEndpointsUpdated) -> None:

        for connection_config in ev.available_endpoints:
            if connection_config.name == self.name:
                continue
            elif self.is_connected_to(connection_config.name):
                continue
            else:
                self.logger.info(
                    "EventBus Endpoint %s connecting to other Endpoint %s",
                    self.name,
                    connection_config.name
                )
                self.connect_to_endpoints_nowait(connection_config)

    def auto_connect_new_announced_endpoints(self) -> None:
        """
        Connect this endpoint to all new endpoints that are announced
        """
        self.subscribe(AvailableEndpointsUpdated, self.connect_to_other_endpoints)

    async def announce_endpoint(self) -> None:
        """
        Announce this endpoint to the :class:`~trinity.endpoint.TrinityMainEventBusEndpoint` so
        that it will be further propagated to all other endpoints, allowing them to connect to us.
        """
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
            # In a perfect world, we should only reach this code once for every endpoint.
            # However, we check `is_connected_to` here as a safe guard because theoretically
            # it could happen that a (buggy, malicious) plugin raises the `EventBusConnected`
            # event multiple times which would then raise an exception if we are already connected
            # to that endpoint.
            if not self.is_connected_to(ev.connection_config.name):
                self.logger.info(
                    "EventBus of main process connecting to EventBus %s", ev.connection_config.name
                )
                await self.connect_to_endpoints(ev.connection_config)

            self.available_endpoints = self.available_endpoints + (ev.connection_config,)
            self.logger.debug("New EventBus Endpoint connected %s", ev.connection_config.name)
            # Broadcast available endpoints to all connected endpoints, giving them
            # a chance to cross connect
            await self.broadcast(AvailableEndpointsUpdated(self.available_endpoints))
            self.logger.debug("Connected EventBus Endpoints %s", self.available_endpoints)

        def spawn_handle_new_endpoints(ev: EventBusConnected) -> None:
            asyncio.ensure_future(handle_new_endpoints(ev))

        self.subscribe(EventBusConnected, spawn_handle_new_endpoints)
