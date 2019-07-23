import asyncio

from lahja import AsyncioEndpoint

from trinity.extensibility.events import PluginStartedEvent

from .plugin import BaseIsolatedPlugin


class AsyncioIsolatedPlugin(BaseIsolatedPlugin):
    _event_bus: AsyncioEndpoint = None
    _loop: asyncio.AbstractEventLoop

    @property
    def event_bus(self) -> AsyncioEndpoint:
        if self._event_bus is None:
            raise AttributeError("Event bus is not available yet")
        return self._event_bus

    def _spawn_start(self) -> None:
        self._setup_logging()

        with self.boot_info.trinity_config.process_id_file(self.normalized_name):
            self._loop = asyncio.get_event_loop()
            asyncio.ensure_future(self._prepare_start())
            self._loop.run_forever()
            self._loop.close()

    async def _prepare_start(self) -> None:
        # prevent circular import
        from trinity.event_bus import AsyncioEventBusService

        self._event_bus_service = AsyncioEventBusService(
            self.boot_info.trinity_config,
            self.normalized_name,
        )
        asyncio.ensure_future(self._event_bus_service.run())
        await self._event_bus_service.wait_event_bus_available()
        self._event_bus = self._event_bus_service.get_event_bus()

        await self.event_bus.broadcast(
            PluginStartedEvent(type(self))
        )

        self.do_start()
