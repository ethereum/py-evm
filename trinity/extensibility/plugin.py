from abc import (
    ABC,
    abstractmethod
)
from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
import asyncio
import logging
from multiprocessing import (
    Process
)
from typing import (
    Any,
    Dict,
    NamedTuple
)

from lahja import (
    BroadcastConfig,
    Endpoint,
)

from trinity.config import (
    TrinityConfig
)
from trinity.constants import (
    MAIN_EVENTBUS_ENDPOINT
)
from trinity.events import (
    ShutdownRequest,
)
from trinity.extensibility.events import (
    BaseEvent,
    PluginStartedEvent,
)
from trinity.extensibility.exceptions import (
    EventBusNotReady,
)
from trinity.utils.ipc import (
    kill_process_gracefully
)
from trinity.utils.mp import (
    ctx,
)
from trinity.utils.logging import (
    setup_queue_logging,
)


class TrinityBootInfo(NamedTuple):
    args: Namespace
    trinity_config: TrinityConfig
    boot_kwargs: Dict[str, Any] = None


class PluginContext:
    """
    The :class:`~trinity.extensibility.plugin.PluginContext` holds valuable contextual information
    and APIs to be used by a plugin. This includes the parsed arguments that were used to launch
    ``Trinity`` as well as an :class:`~lahja.endpoint.Endpoint` that the plugin can use to connect
    to the central :class:`~lahja.eventbus.EventBus`.

    The :class:`~trinity.extensibility.plugin.PluginContext` is set during startup and is
    guaranteed to exist by the time that a plugin receives its
    :meth:`~trinity.extensibility.plugin.BasePlugin.ready` call.
    """

    def __init__(self, endpoint: Endpoint, boot_info: TrinityBootInfo) -> None:
        self._event_bus = endpoint
        self._args: Namespace = boot_info.args
        self._trinity_config: TrinityConfig = boot_info.trinity_config
        # Leaving boot_kwargs as an undocumented public member as it will most likely go away
        self.boot_kwargs: Dict[str, Any] = boot_info.boot_kwargs

    def shutdown_host(self, reason: str) -> None:
        """
        Shutdown ``Trinity`` by broadcasting a :class:`~trinity.events.ShutdownRequest` on the
        :class:`~lahja.eventbus.EventBus`. The actual shutdown routine is executed and coordinated
        by the main application process who listens for this event.
        """
        self.event_bus.broadcast(
            ShutdownRequest(reason),
            BroadcastConfig(filter_endpoint=MAIN_EVENTBUS_ENDPOINT)
        )

    @property
    def args(self) -> Namespace:
        """
        Return the parsed arguments that were used to launch the application
        """
        return self._args

    @property
    def event_bus(self) -> Endpoint:
        """
        Return the :class:`~lahja.endpoint.Endpoint` that the plugin uses to connect to the
        central :class:`~lahja.eventbus.EventBus`
        """
        return self._event_bus

    @property
    def trinity_config(self) -> TrinityConfig:
        """
        Return the :class:`~trinity.config.TrinityConfig`
        """
        return self._trinity_config


class BasePlugin(ABC):

    context: PluginContext = None
    running: bool = False

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Describe the name of the plugin.
        """
        raise NotImplementedError(
            "Must be implemented by subclasses"
        )

    @property
    def logger(self) -> logging.Logger:
        """
        Get the :class:`~logging.Logger` for this plugin.
        """
        return logging.getLogger('trinity.extensibility.plugin.BasePlugin#{0}'.format(self.name))

    @property
    def event_bus(self) -> Endpoint:
        """
        Get the :class:`~lahja.endpoint.Endpoint` that this plugin uses to connect to the
        :class:`~lahja.eventbus.EventBus`
        """
        if self.context is None:
            raise EventBusNotReady("Tried accessing ``event_bus`` before ``ready`` was called")

        return self.context.event_bus

    def set_context(self, context: PluginContext) -> None:
        """
        Set the :class:`~trinity.extensibility.plugin.PluginContext` for this plugin.
        """
        self.context = context

    def ready(self) -> None:
        """
        Notify the plugin that it is ready to bootstrap itself. Plugins can rely
        on the :class:`~trinity.extensibility.plugin.PluginContext` to be set
        after this method has been called.
        """
        pass

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        """
        Give the plugin a chance to amend the Trinity CLI argument parser. This hook is called
        before :meth:`~trinity.extensibility.plugin.BasePlugin.ready`
        """
        pass

    def start(self) -> None:
        """
        Delegate to :meth:`~trinity.extensibility.plugin.BasePlugin._start` and set ``running``
        to ``True``. Broadcast a :class:`~trinity.extensibility.events.PluginStartedEvent` on the
        :class:`~lahja.eventbus.EventBus` and hence allow other plugins to act accordingly.
        """
        self.running = True
        self._start()
        self.event_bus.broadcast(
            PluginStartedEvent(type(self))
        )
        self.logger.info("Plugin started: %s", self.name)

    def _start(self) -> None:
        """
        Perform the actual plugin start routine. In the case of a `BaseIsolatedPlugin` this method
        will be called in a separate process.

        This method should usually be overwritten by subclasses with the exception of plugins that
        set ``func`` on the ``ArgumentParser`` to redefine the entire host program.
        """
        pass


class BaseSyncStopPlugin(BasePlugin):
    """
    A :class:`~trinity.extensibility.plugin.BaseSyncStopPlugin` unwinds synchronoulsy, hence blocks
    until the shutdown is done.
    """
    def _stop(self) -> None:
        """
        Stop the plugin. Should be overwritten by subclasses.
        """
        pass

    def stop(self) -> None:
        """
        Delegate to :meth:`~trinity.extensibility.plugin.BaseSyncStopPlugin._stop` causing the
        plugin to stop and setting ``running`` to ``False``.
        """
        self._stop()
        self.running = False


class BaseAsyncStopPlugin(BasePlugin):
    """
    A :class:`~trinity.extensibility.plugin.BaseAsyncStopPlugin` unwinds asynchronoulsy, hence
    needs to be awaited.
    """

    async def _stop(self) -> None:
        """
        Asynchronously stop the plugin. Should be overwritten by subclasses.
        """
        pass

    async def stop(self) -> None:
        """
        Delegate to :meth:`~trinity.extensibility.plugin.BaseAsyncStopPlugin._stop` causing the
        plugin to stop asynchronously and setting ``running`` to ``False``.
        """
        await self._stop()
        self.running = False


class BaseMainProcessPlugin(BasePlugin):
    """
    A :class:`~trinity.extensibility.plugin.BaseMainProcessPlugin` overtakes the whole main process
    early before any of the subsystems started. In that sense it redefines the whole meaning of the
    ``trinity`` command.
    """
    pass


class BaseIsolatedPlugin(BaseSyncStopPlugin):
    """
    A :class:`~trinity.extensibility.plugin.BaseIsolatedPlugin` runs in an isolated process and
    hence provides security and flexibility by not making assumptions about its internal
    operations.

    Such plugins are free to use non-blocking asyncio as well as synchronous calls. When an
    isolated plugin is stopped it does first receive a SIGINT followed by a SIGTERM soon after.
    It is up to the plugin to handle these signals accordingly.
    """

    _process: Process = None

    def start(self) -> None:
        """
        Prepare the plugin to get started and eventually call ``_start`` in a separate process.
        """
        self.running = True
        self._process = ctx.Process(
            target=self._prepare_start,
        )

        self._process.start()
        self.logger.info("Plugin started: %s", self.name)

    def _prepare_start(self) -> None:
        log_queue = self.context.boot_kwargs['log_queue']
        level = self.context.boot_kwargs.get('log_level', logging.INFO)
        setup_queue_logging(log_queue, level)
        self.event_bus.connect_no_wait()
        self.event_bus.broadcast(
            PluginStartedEvent(type(self))
        )
        self._start()

    def _stop(self) -> None:
        self.context.event_bus.stop()
        kill_process_gracefully(self._process, self.logger)


class DebugPlugin(BaseAsyncStopPlugin):
    """
    This is a dummy plugin useful for demonstration and debugging purposes
    """

    @property
    def name(self) -> str:
        return "Debug Plugin"

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        arg_parser.add_argument("--debug-plugin", type=bool, required=False)

    def handle_event(self, activation_event: BaseEvent) -> None:
        self.logger.info("Debug plugin: handle_event called: %s", activation_event)

    def _start(self) -> None:
        self.logger.info("Debug plugin: start called")
        asyncio.ensure_future(self.count_forever())

    async def count_forever(self) -> None:
        i = 0
        while True:
            self.logger.info(i)
            i += 1
            await asyncio.sleep(1)

    async def _stop(self) -> None:
        self.logger.info("Debug plugin: stop called")
