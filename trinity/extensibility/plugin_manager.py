from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
import logging
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Type,
)

from trinity.config import (
    TrinityConfig
)
from trinity.endpoint import (
    TrinityEventBusEndpoint,
    TrinityMainEventBusEndpoint,
)
from trinity.extensibility.plugin import (
    BaseIsolatedPlugin,
    BasePlugin,
    TrinityBootInfo,
)
from trinity._utils.ipc import (
    kill_processes_gracefully,
)


class PluginManager:
    """
    The plugin manager is responsible for managing the life cycle of any available
    plugins.

    A :class:`~trinity.extensibility.plugin_manager.PluginManager` is tight to a specific
    :class:`~trinity.extensibility.plugin_manager.BaseManagerProcessScope` which defines which
    plugins are controlled by this specific manager instance.

    This is due to the fact that Trinity currently allows plugins to either run in a shared
    process, also known as the "networking" process, as well as in their own isolated
    processes.

    Trinity uses two different :class:`~trinity.extensibility.plugin_manager.PluginManager`
    instances to govern these different categories of plugins.

      .. note::

        This API is very much in flux and is expected to change heavily.
    """

    def __init__(self,
                 endpoint: TrinityMainEventBusEndpoint,
                 plugins: Iterable[Type[BasePlugin]]) -> None:
        self._endpoint = endpoint
        self._registered_plugins: List[Type[BasePlugin]] = list(plugins)
        self._plugin_store: List[BasePlugin] = []
        self._logger = logging.getLogger("trinity.extensibility.plugin_manager.PluginManager")

    @property
    def event_bus_endpoint(self) -> TrinityEventBusEndpoint:
        """
        Return the :class:`~lahja.endpoint.Endpoint` that the
        :class:`~trinity.extensibility.plugin_manager.PluginManager` instance uses to connect to
        the event bus.
        """
        return self._endpoint

    def amend_argparser_config(self,
                               arg_parser: ArgumentParser,
                               subparser: _SubParsersAction) -> None:
        """
        Call :meth:`~trinity.extensibility.plugin.BasePlugin.configure_parser` for every registered
        plugin, giving them the option to amend the global parser setup.
        """
        for plugin_type in self._registered_plugins:
            plugin_type.configure_parser(arg_parser, subparser)

    def prepare(self,
                args: Namespace,
                trinity_config: TrinityConfig,
                boot_kwargs: Dict[str, Any] = None) -> None:
        """
        Create all plugins and call :meth:`~trinity.extensibility.plugin.BasePlugin.ready` on each
        of them.
        """
        for plugin_type in self._registered_plugins:

            plugin = plugin_type(TrinityBootInfo(args, trinity_config, boot_kwargs))
            plugin.ready(self.event_bus_endpoint)

            self._plugin_store.append(plugin)

    def shutdown_blocking(self) -> None:
        """
        Synchronously shut down all running plugins.
        """

        self._logger.info("Shutting down PluginManager")

        plugins = [
            plugin for plugin in self._plugin_store
            if isinstance(plugin, BaseIsolatedPlugin) and plugin.running
        ]
        processes = [plugin.process for plugin in plugins]

        for plugin in plugins:
            self._logger.info("Stopping plugin: %s", plugin.name)

        kill_processes_gracefully(processes, self._logger)

        for plugin in plugins:
            self._logger.info("Successfully stopped plugin: %s", plugin.name)
