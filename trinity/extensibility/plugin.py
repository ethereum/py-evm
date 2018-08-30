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
)

from lahja import (
    BroadcastConfig,
    Endpoint,
)

from trinity.config import (
    ChainConfig
)
from trinity.constants import (
    MAIN_EVENTBUS_ENDPOINT
)
from trinity.events import (
    ShutdownRequest
)
from trinity.extensibility.events import (
    BaseEvent
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


class PluginProcessScope(Enum):
    """
    Define the process model in which a plugin operates:

      - ISOLATED: The plugin runs in its own separate process
      - MAIN: The plugin takes over the Trinity main process (e.g. attach)
      - SHARED: The plugin runs in a process that is shared with other plugins
    """

    ISOLATED = auto()
    MAIN = auto()
    SHARED = auto()


class PluginContext:
    """
    The ``PluginContext`` holds valuable contextual information such as the parsed
    arguments that were used to launch ``Trinity``. It also provides access to APIs
    such as the ``EventBus``.

    Each plugin gets a ``PluginContext`` injected during startup.
    """

    def __init__(self, endpoint: Endpoint) -> None:
        self.event_bus = endpoint
        self.boot_kwargs: Dict[str, Any] = None
        self.args: Namespace = None
        self.chain_config: ChainConfig = None

    def shutdown_host(self) -> None:
        self.event_bus.broadcast(
            ShutdownRequest(),
            BroadcastConfig(filter_endpoint=MAIN_EVENTBUS_ENDPOINT)
        )


class BasePlugin(ABC):

    context: PluginContext = None

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Describe the name of the plugin
        """
        raise NotImplementedError(
            "Must be implemented by subclasses"
        )

    @property
    def process_scope(self) -> PluginProcessScope:
        """
        Return the :class:`~trinity.extensibility.plugin.PluginProcessScope` that the plugin uses
        to operate. The default scope is ``PluginProcessScope.SHARED``.
        """
        return PluginProcessScope.SHARED

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger('trinity.extensibility.plugin.BasePlugin#{0}'.format(self.name))

    def set_context(self, context: PluginContext) -> None:
        """
        Set the :class:`~trinity.extensibility.plugin.PluginContext` for this plugin.
        """
        self.context = context

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        """
        Called at startup, giving the plugin a chance to amend the Trinity CLI argument parser
        """
        pass

    def handle_event(self, activation_event: BaseEvent) -> None:
        """
        Notify the plugin about an event, giving it the chance to do internal accounting right
        before :meth:`~trinity.extensibility.plugin.BasePlugin.should_start` is called
        """

        pass

    def should_start(self) -> bool:
        """
        Return ``True`` if the plugin should start, otherwise return ``False``
        """

        return False

    def _start(self) -> None:
        self.start()

    def start(self) -> None:
        """
        The ``start`` method is called only once when the plugin is started. In the case
        of an `BaseIsolatedPlugin` this method will be launched in a separate process.
        """
        pass

    def stop(self) -> None:
        """
        Called when the plugin gets stopped. Should be overwritten to perform cleanup
        work in case the plugin set up external resources.
        """
        pass


class BaseIsolatedPlugin(BasePlugin):

    _process: Process = None

    @property
    def process_scope(self) -> PluginProcessScope:
        return PluginProcessScope.ISOLATED

    def _start(self) -> None:
        self._process = ctx.Process(
            target=self._prepare_start,
        )

        self._process.start()

    def _prepare_start(self) -> None:
        log_queue = self.context.boot_kwargs['log_queue']
        level = self.context.boot_kwargs.get('log_level', logging.INFO)
        setup_queue_logging(log_queue, level)

        self.start()

    def stop(self) -> None:
        self.context.event_bus.stop()
        kill_process_gracefully(self._process, self.logger)


class DebugPlugin(BasePlugin):
    """
    This is a dummy plugin useful for demonstration and debugging purposes
    """

    @property
    def name(self) -> str:
        return "Debug Plugin"

    def configure_parser(self, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        arg_parser.add_argument("--debug-plugin", type=bool, required=False)

    def handle_event(self, activation_event: BaseEvent) -> None:
        self.logger.info("Debug plugin: handle_event called: ", activation_event)

    def should_start(self) -> bool:
        self.logger.info("Debug plugin: should_start called")
        return True

    def start(self) -> None:
        self.logger.info("Debug plugin: start called")
