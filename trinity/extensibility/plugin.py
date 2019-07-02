from abc import (
    ABC,
    abstractmethod
)
from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
from enum import (
    auto,
    Enum,
)
import logging
from multiprocessing import (
    Process
)
from typing import (
    Any,
    Dict,
    NamedTuple,
)

from trinity.config import (
    TrinityConfig
)
from trinity.endpoint import (
    TrinityEventBusEndpoint,
)
from trinity.extensibility.events import (
    PluginStartedEvent,
)
from trinity.extensibility.exceptions import (
    InvalidPluginStatus,
)
from trinity._utils.mp import (
    ctx,
)
from trinity._utils.logging import (
    setup_log_levels,
    setup_queue_logging,
)
from trinity._utils.os import (
    friendly_filename_or_url,
)


class PluginStatus(Enum):
    NOT_READY = auto()
    READY = auto()
    STARTED = auto()
    STOPPED = auto()


INVALID_START_STATUS = (PluginStatus.NOT_READY, PluginStatus.STARTED,)


class TrinityBootInfo(NamedTuple):
    args: Namespace
    trinity_config: TrinityConfig
    boot_kwargs: Dict[str, Any] = None


class BasePlugin(ABC):

    _status: PluginStatus = PluginStatus.NOT_READY

    def __init__(self, boot_info: TrinityBootInfo) -> None:
        self.boot_info = boot_info

    @property
    @abstractmethod
    def event_bus(self) -> TrinityEventBusEndpoint:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Describe the name of the plugin.
        """
        pass

    @property
    def normalized_name(self) -> str:
        """
        The normalized (computer readable) name of the plugin
        """
        return friendly_filename_or_url(self.name)

    @classmethod
    def get_logger(cls) -> logging.Logger:
        return logging.getLogger(f'trinity.extensibility.plugin(#{cls.__name__})')

    @property
    def logger(self) -> logging.Logger:
        return self.get_logger()

    @property
    def running(self) -> bool:
        """
        Return ``True`` if the ``status`` is ``PluginStatus.STARTED``, otherwise return ``False``.
        """
        return self._status is PluginStatus.STARTED

    @property
    def status(self) -> PluginStatus:
        """
        Return the current :class:`~trinity.extensibility.plugin.PluginStatus` of the plugin.
        """
        return self._status

    def ready(self, manager_eventbus: TrinityEventBusEndpoint) -> None:
        """
        Set the ``status`` to ``PluginStatus.READY`` and delegate to
        :meth:`~trinity.extensibility.plugin.BasePlugin.on_ready`
        """
        self._status = PluginStatus.READY
        self.on_ready(manager_eventbus)

    def on_ready(self, manager_eventbus: TrinityEventBusEndpoint) -> None:
        """
        Notify the plugin that it is ready to bootstrap itself.
        The ``manager_eventbus`` refers to the instance of the
        :class:`~lahja.endpoint.Endpoint` that the
        :class:`~trinity.extensibility.plugin_manager.PluginManager` uses which may or may not
        be the same :class:`~lahja.endpoint.Endpoint` as the plugin uses depending on the type
        of the plugin. The plugin should use this :class:`~lahja.endpoint.Endpoint` instance to
        listen for events *before* the plugin has started.
        """
        pass

    @classmethod
    def configure_parser(cls, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        """
        Give the plugin a chance to amend the Trinity CLI argument parser. This hook is called
        before :meth:`~trinity.extensibility.plugin.BasePlugin.on_ready`
        """
        pass

    def start(self) -> None:
        """
        Delegate to :meth:`~trinity.extensibility.plugin.BasePlugin.do_start` and set ``running``
        to ``True``. Broadcast a :class:`~trinity.extensibility.events.PluginStartedEvent` on the
        event bus and hence allow other plugins to act accordingly.
        """

        if self._status in INVALID_START_STATUS:
            raise InvalidPluginStatus(
                f"Can not start plugin when the plugin status is {self.status}"
            )

        self._status = PluginStatus.STARTED
        self.do_start()
        self.event_bus.broadcast_nowait(
            PluginStartedEvent(type(self))
        )
        self.logger.info("Plugin started: %s", self.name)

    def do_start(self) -> None:
        """
        Perform the actual plugin start routine. In the case of a `BaseIsolatedPlugin` this method
        will be called in a separate process.

        This method should usually be overwritten by subclasses with the exception of plugins that
        set ``func`` on the ``ArgumentParser`` to redefine the entire host program.
        """
        pass


class BaseMainProcessPlugin(BasePlugin):
    """
    A :class:`~trinity.extensibility.plugin.BaseMainProcessPlugin` overtakes the whole main process
    early before any of the subsystems started. In that sense it redefines the whole meaning of the
    ``trinity`` command.
    """

    @property
    def event_bus(self) -> TrinityEventBusEndpoint:
        raise NotImplementedError('BaseMainProcessPlugins do not have event busses')


class BaseIsolatedPlugin(BasePlugin):
    """
    A :class:`~trinity.extensibility.plugin.BaseIsolatedPlugin` runs in an isolated process and
    hence provides security and flexibility by not making assumptions about its internal
    operations.

    Such plugins are free to use non-blocking asyncio as well as synchronous calls. When an
    isolated plugin is stopped it does first receive a SIGINT followed by a SIGTERM soon after.
    It is up to the plugin to handle these signals accordingly.
    """
    _process: Process = None
    _event_bus: TrinityEventBusEndpoint = None

    @property
    def process(self) -> Process:
        """
        Return the ``Process`` created by the isolated plugin.
        """
        return self._process

    def start(self) -> None:
        """
        Prepare the plugin to get started and eventually call ``do_start`` in a separate process.
        """
        self._status = PluginStatus.STARTED
        self._process = ctx.Process(
            target=self._spawn_start,
        )

        self._process.start()
        self.logger.info("Plugin started: %s (pid=%d)", self.name, self._process.pid)

    @abstractmethod
    def _spawn_start(self) -> None:
        pass

    def stop(self) -> None:
        """
        Set the ``status`` to `STOPPED`` but rely on the
        :class:`~trinity.extensibility.plugin_manager.PluginManager` to tear down the process. This
        allows isolated plugins to be taken down concurrently without depending on a running
        event loop.
        """
        self._status = PluginStatus.STOPPED

    def _setup_logging(self) -> None:
        log_queue = self.boot_info.boot_kwargs['log_queue']
        level = self.boot_info.boot_kwargs.get('log_level', logging.INFO)
        setup_queue_logging(log_queue, level)
        if self.boot_info.args.log_levels:
            setup_log_levels(self.boot_info.args.log_levels)
