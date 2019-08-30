import asyncio
from typing import (
    Any,
    Callable,
    Sequence,
    Type,
    Tuple,
)

from lahja import AsyncioEndpoint, ConnectionConfig, BroadcastConfig, EndpointAPI

from cancel_token import CancelToken

from p2p.service import BaseService

from trinity.config import TrinityConfig
from trinity.constants import (
    MAIN_EVENTBUS_ENDPOINT,
)
from trinity.events import (
    ShutdownRequest,
    AvailableEndpointsUpdated,
    EventBusConnected,
)
from trinity.extensibility import (
    BasePlugin,
    PluginManager,
    TrinityBootInfo,
)


class PluginManagerService(BaseService):
    _endpoint: EndpointAPI

    def __init__(self,
                 trinity_boot_info: TrinityBootInfo,
                 plugins: Sequence[Type[BasePlugin]],
                 kill_trinity_fn: Callable[[str], Any],
                 cancel_token: CancelToken = None,
                 loop: asyncio.AbstractEventLoop = None) -> None:
        self._boot_info = trinity_boot_info
        self._plugins = plugins
        self._kill_trinity_fn = kill_trinity_fn
        super().__init__(cancel_token, loop)

    async def _run(self) -> None:
        self._connection_config = ConnectionConfig.from_name(
            MAIN_EVENTBUS_ENDPOINT,
            self._boot_info.trinity_config.ipc_dir
        )
        async with AsyncioEndpoint.serve(self._connection_config) as endpoint:
            self._endpoint = endpoint

            # start the background process that tracks and propagates available
            # endpoints to the other connected endpoints
            self.run_daemon_task(self._track_and_propagate_available_endpoints())
            self.run_daemon_task(self._handle_shutdown_request())

            # start the plugin manager
            self.plugin_manager = PluginManager(endpoint, self._plugins)
            self.plugin_manager.prepare(self._boot_info)
            await self.cancellation()

    async def _handle_shutdown_request(self) -> None:
        req = await self.wait(self._endpoint.wait_for(ShutdownRequest))
        self._kill_trinity_fn(req.reason)
        self.cancel_nowait()

    async def _cleanup(self) -> None:
        self.plugin_manager.shutdown_blocking()

    _available_endpoints: Tuple[ConnectionConfig, ...] = ()

    async def _track_and_propagate_available_endpoints(self) -> None:
        """
        Track new announced endpoints and propagate them across all other existing endpoints.
        """
        async for ev in self.wait_iter(self._endpoint.stream(EventBusConnected)):
            self._available_endpoints = self._available_endpoints + (ev.connection_config,)
            self.logger.debug("New EventBus Endpoint connected %s", ev.connection_config.name)
            # Broadcast available endpoints to all connected endpoints, giving them
            # a chance to cross connect
            await self._endpoint.broadcast(AvailableEndpointsUpdated(self._available_endpoints))
            self.logger.debug("Connected EventBus Endpoints %s", self._available_endpoints)


class AsyncioEventBusService(BaseService):
    endpoint: AsyncioEndpoint

    def __init__(self,
                 trinity_config: TrinityConfig,
                 endpoint_name: str,
                 cancel_token: CancelToken = None,
                 loop: asyncio.AbstractEventLoop = None) -> None:
        self._trinity_config = trinity_config
        self._endpoint_available = asyncio.Event()
        self._connection_config = ConnectionConfig.from_name(
            endpoint_name,
            self._trinity_config.ipc_dir
        )
        super().__init__(cancel_token, loop)

    async def wait_event_bus_available(self) -> None:
        await self._endpoint_available.wait()

    def get_event_bus(self) -> AsyncioEndpoint:
        return self._endpoint

    async def _run(self) -> None:
        async with AsyncioEndpoint.serve(self._connection_config) as endpoint:
            self._endpoint = endpoint
            # signal that the endpoint is now available
            self._endpoint_available.set()

            # run background task that automatically connects to newly announced endpoints
            self.run_daemon_task(self._auto_connect_new_announced_endpoints())

            # connect to the *main* endpoint which communicates information
            # about other endpoints that come online.
            main_endpoint_config = ConnectionConfig.from_name(
                MAIN_EVENTBUS_ENDPOINT,
                self._trinity_config.ipc_dir,
            )
            await endpoint.connect_to_endpoints(main_endpoint_config)

            # announce ourself to the event bus
            await endpoint.wait_until_endpoint_subscribed_to(
                MAIN_EVENTBUS_ENDPOINT,
                EventBusConnected,
            )
            await endpoint.broadcast(
                EventBusConnected(self._connection_config),
                BroadcastConfig(filter_endpoint=MAIN_EVENTBUS_ENDPOINT)
            )

            # run until the endpoint exits
            await self.cancellation()

    async def _auto_connect_new_announced_endpoints(self) -> None:
        """
        Connect this endpoint to all new endpoints that are announced
        """
        async for ev in self.wait_iter(self._endpoint.stream(AvailableEndpointsUpdated)):
            # We only connect to Endpoints that appear after our own Endpoint in the set.
            # This ensures that we don't try to connect to an Endpoint while that remote
            # Endpoint also wants to connect to us.
            endpoints_to_connect_to = tuple(
                connection_config
                for index, val in enumerate(ev.available_endpoints)
                if val.name == self._endpoint.name
                for connection_config in ev.available_endpoints[index:]
                if not self._endpoint.is_connected_to(connection_config.name)
            )
            self._endpoint.logger.info(
                "EventBus Endpoint %s connecting to other Endpoints %s",
                self._endpoint.name,
                ','.join((config.name for config in endpoints_to_connect_to)),
            )
            await self._endpoint.connect_to_endpoints(*endpoints_to_connect_to)
