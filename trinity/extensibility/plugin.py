from abc import (
    ABC,
    abstractmethod
)
from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
from enum import (
    auto,
    Enum,
)
import logging
from typing import (
    Any,
    Dict,
)

from lahja import (
    Endpoint
)

from trinity.extensibility.events import (
    BaseEvent
)
from trinity.utils.mp import (
    ctx,
)
from trinity.utils.logging import (
    setup_queue_logging,
)


class PluginProcessScope(Enum):

    SHARED = auto()
    MAIN = auto()
    OWN = auto()


class PluginContext:

    def __init__(self, endpoint: Endpoint, boot_kwargs: Dict[str, Any] = None) -> None:
        self.event_bus = endpoint
        self.boot_kwargs = boot_kwargs


class BasePlugin(ABC):

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
        return PluginProcessScope.SHARED

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger('trinity.extensibility.plugin.BasePlugin#{0}'.format(self.name))

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

    def start(self, context: PluginContext) -> None:
        """
        The ``start`` method is called only once when the plugin is started
        """
        pass

    def stop(self) -> None:
        """
        Called when the plugin gets stopped. Should be overwritten to perform cleanup
        work in case the plugin set up external resources.
        """
        pass


class BaseOwnProcessPlugin(BasePlugin):

    @property
    def process_scope(self) -> PluginProcessScope:
        return PluginProcessScope.OWN

    def start(self, context: PluginContext) -> None:
        proc = ctx.Process(
            target=self._launch_process,
            args=(
                context.event_bus,
            ),
            kwargs=context.boot_kwargs
        )

        proc.start()

    @classmethod
    def _launch_process(cls, event_bus: Endpoint, **kwargs: Any) -> None:
        log_queue = kwargs['log_queue']
        level = kwargs.get('log_level', logging.INFO)
        setup_queue_logging(log_queue, level)

        cls.launch_process(event_bus)

    @staticmethod
    @abstractmethod
    def launch_process(event_bus: Endpoint, **kwargs: Any) -> None:
        pass


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

    def start(self, context: PluginContext) -> None:
        self.logger.info("Debug plugin: start called")
