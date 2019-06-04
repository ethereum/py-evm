import asyncio

from lahja import ConnectionConfig

from trinity.constants import MAIN_EVENTBUS_ENDPOINT
from trinity.extensibility.events import PluginStartedEvent
from trinity.endpoint import TrinityEventBusEndpoint

from .plugin import BaseIsolatedPlugin


class AsyncioIsolatedPlugin(BaseIsolatedPlugin):
    _event_bus: TrinityEventBusEndpoint = None

    @property
    def event_bus(self) -> TrinityEventBusEndpoint:
        if self._event_bus is None:
            self._event_bus = TrinityEventBusEndpoint(self.normalized_name)
        return self._event_bus

    def _spawn_start(self) -> None:
        self._setup_logging()

        with self.boot_info.trinity_config.process_id_file(self.normalized_name):
            loop = asyncio.get_event_loop()
            asyncio.ensure_future(self._prepare_start())
            loop.run_forever()
            loop.close()

    async def _prepare_start(self) -> None:
        connection_config = ConnectionConfig.from_name(
            self.normalized_name,
            self.boot_info.trinity_config.ipc_dir,
        )
        await self.event_bus.start()
        await self.event_bus.start_server(connection_config.path)
        await self.event_bus.connect_to_endpoints(
            ConnectionConfig.from_name(
                MAIN_EVENTBUS_ENDPOINT, self.boot_info.trinity_config.ipc_dir
            )
        )
        # This makes the `main` process aware of this Endpoint which will then propagate the info
        # so that every other Endpoint can connect directly to the plugin Endpoint
        await self.event_bus.announce_endpoint()
        await self.event_bus.broadcast(
            PluginStartedEvent(type(self))
        )

        # Whenever new EventBus Endpoints come up the `main` process broadcasts this event
        # and we connect to every Endpoint directly
        asyncio.ensure_future(self.event_bus.auto_connect_new_announced_endpoints())

        self.do_start()
