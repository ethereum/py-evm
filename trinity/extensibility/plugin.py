from abc import (
    ABC,
    abstractmethod
)
from argparse import (
    ArgumentParser
)
import logging
from typing import (
    Any
)

from trinity.extensibility.events import (
    BaseEvent
)

# TODO: we spec this out later
PluginContext = Any


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
    def logger(self) -> logging.Logger:
        return logging.getLogger('trinity.extensibility.plugin.BasePlugin#{0}'.format(self.name))

    @abstractmethod
    def configure_parser(self, arg_parser: ArgumentParser) -> None:
        """
        Called at startup, giving the plugin a chance to amend the Trinity CLI argument parser
        """
        raise NotImplementedError(
            "Must be implemented by subclasses"
        )

    @abstractmethod
    def handle_event(self, activation_event: BaseEvent) -> None:
        """
        Notify the plugin about an event, giving it the chance to do internal accounting right
        before :meth:`~trinity.extensibility.plugin.BasePlugin.should_start` is called
        """

        raise NotImplementedError(
            "Must be implemented by subclasses"
        )

    @abstractmethod
    def should_start(self) -> bool:
        """
        Return ``True`` if the plugin should start, otherwise return ``False``
        """

        raise NotImplementedError(
            "Must be implemented by subclasses"
        )

    @abstractmethod
    def start(self, context: PluginContext) -> None:
        """
        The ``start`` method is called only once when the plugin is started
        """
        raise NotImplementedError(
            "Must be implemented by subclasses"
        )

    def stop(self) -> None:
        """
        Called when the plugin gets stopped. Should be overwritten to perform cleanup
        work in case the plugin set up external resources.
        """
        pass


class DebugPlugin(BasePlugin):
    """
    This is a dummy plugin useful for demonstration and debugging purposes
    """

    @property
    def name(self) -> str:
        return "Debug Plugin"

    def configure_parser(self, arg_parser: ArgumentParser) -> None:
        arg_parser.add_argument("--debug-plugin", type=bool, required=False)

    def handle_event(self, activation_event: BaseEvent) -> None:
        self.logger.info("Debug plugin: handle_event called: ", activation_event)

    def should_start(self) -> bool:
        self.logger.info("Debug plugin: should_start called")
        return True

    def start(self, context: PluginContext) -> None:
        self.logger.info("Debug plugin: start called")
