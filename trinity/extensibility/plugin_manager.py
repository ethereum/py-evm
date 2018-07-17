from argparse import (
    ArgumentParser,
    _SubParsersAction,
)
import logging
from typing import (
    Iterable,
    List,
    Union,
)

from trinity.extensibility.events import (
    BaseEvent,
    PluginStartedEvent,
)
from trinity.extensibility.plugin import (
    BasePlugin,
)


class PluginManager:
    """
    The plugin manager is responsible to register, keep and manage the life cycle of any available
    plugins.

      .. note::

        This API is very much in flux and is expected to change heavily.
    """

    def __init__(self) -> None:
        self._plugin_store: List[BasePlugin] = []
        self._started_plugins: List[BasePlugin] = []
        self._logger = logging.getLogger("trinity.extensibility.plugin_manager.PluginManager")

    def register(self, plugins: Union[BasePlugin, Iterable[BasePlugin]]) -> None:
        """
        Register one or multiple instances of :class:`~trinity.extensibility.plugin.BasePlugin`
        with the plugin manager.
        """

        new_plugins = [plugins] if isinstance(plugins, BasePlugin) else plugins
        self._plugin_store.extend(new_plugins)

    def amend_argparser_config(self,
                               arg_parser: ArgumentParser,
                               subparser: _SubParsersAction) -> None:
        """
        Call :meth:`~trinity.extensibility.plugin.BasePlugin.configure_parser` for every registered
        plugin, giving them the option to amend the global parser setup.
        """
        for plugin in self._plugin_store:
            plugin.configure_parser(arg_parser, subparser)

    def broadcast(self, event: BaseEvent, exclude: BasePlugin = None) -> None:
        """
        Notify every registered :class:`~trinity.extensibility.plugin.BasePlugin` about an
        event and check whether the plugin wants to start based on that event.

        If a plugin gets started it will cause a
        :class:`~trinity.extensibility.events.PluginStartedEvent` to get
        broadcasted to all other plugins, giving them the chance to start based on that.
        """
        for plugin in self._plugin_store:

            if plugin is exclude:
                continue

            plugin.handle_event(event)

            if plugin in self._started_plugins:
                continue

            if not plugin.should_start():
                continue

            plugin.start(None)
            self._started_plugins.append(plugin)
            self._logger.info("Plugin started: {}".format(plugin.name))
            self.broadcast(PluginStartedEvent(plugin), plugin)
