from abc import (
    ABC,
    abstractmethod,
)
from argparse import (
    ArgumentParser,
    Namespace,
    _SubParsersAction,
)
import asyncio
import logging
from typing import (
    Any,
    Awaitable,
    cast,
    Dict,
    Iterable,
    List,
    Optional,
    Type,
    TypeVar,
)

from trinity.config import (
    TrinityConfig
)
from trinity.endpoint import (
    TrinityEventBusEndpoint,
    TrinityMainEventBusEndpoint,
)
from trinity.extensibility.exceptions import (
    UnsuitableShutdownError,
)
from trinity.extensibility.plugin import (
    BaseAsyncStopPlugin,
    BaseIsolatedPlugin,
    BaseMainProcessPlugin,
    BasePlugin,
    TrinityBootInfo,
)
from trinity._utils.ipc import (
    kill_processes_gracefully,
)


TPlugin = TypeVar('TPlugin', bound=BasePlugin)


class BaseManagerProcessScope(ABC):
    """
    Define the operational model under which a
    :class:`~trinity.extensibility.plugin_manager.PluginManager` works. Subclasses
    define whether a :class:`~trinity.extensibility.plugin_manager.PluginManager` is
    responsible to manage a specific plugin and how it is created.
    """

    endpoint: TrinityEventBusEndpoint

    @abstractmethod
    def is_responsible_for_plugin(self, plugin: Type[BasePlugin]) -> bool:
        """
        Define whether a :class:`~trinity.extensibility.plugin_manager.PluginManager` operating
        under this scope is responsible to manage the given ``plugin``.
        """
        pass

    @abstractmethod
    def create_plugin(self,
                      plugin_type: Type[TPlugin],
                      boot_info: TrinityBootInfo) -> TPlugin:
        """
        Instantiate the given plugin.
        """
        pass


class MainAndIsolatedProcessScope(BaseManagerProcessScope):

    def __init__(self, main_proc_endpoint: TrinityMainEventBusEndpoint) -> None:
        self.endpoint = main_proc_endpoint

    def is_responsible_for_plugin(self, plugin: Type[BasePlugin]) -> bool:
        """
        Return ``True`` if if the plugin instance is a subclass of
        :class:`~trinity.extensibility.plugin.BaseIsolatedPlugin` or
        :class:`~trinity.extensibility.plugin.BaseMainProcessPlugin`
        """
        return issubclass(plugin, BaseIsolatedPlugin) or issubclass(plugin, BaseMainProcessPlugin)

    def create_plugin(self,
                      plugin_type: Type[TPlugin],
                      boot_info: TrinityBootInfo) -> TPlugin:
        return plugin_type(boot_info)


class SharedProcessScope(BaseManagerProcessScope):

    def __init__(self, shared_proc_endpoint: TrinityEventBusEndpoint) -> None:
        self.endpoint = shared_proc_endpoint

    def is_responsible_for_plugin(self, plugin: Type[BasePlugin]) -> bool:
        """
        Return ``True`` if if the plugin instance is a subclass of
        :class:`~trinity.extensibility.plugin.BaseAsyncStopPlugin`.
        """
        return issubclass(plugin, BaseAsyncStopPlugin)

    def create_plugin(self,
                      plugin_type: Type[TPlugin],
                      boot_info: TrinityBootInfo) -> TPlugin:
        # Plugins that run in a shared process all share the endpoint of the plugin manager
        assert issubclass(plugin_type, BaseAsyncStopPlugin)
        return cast(TPlugin, plugin_type(boot_info, self.endpoint))


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
                 scope: BaseManagerProcessScope,
                 plugins: Iterable[Type[BasePlugin]]) -> None:
        self._scope = scope
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
        return self._scope.endpoint

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
        Create all plugins which this manager is responsible for and call
        :meth:`~trinity.extensibility.plugin.BasePlugin.ready` on each of them.
        """
        for plugin_type in self._registered_plugins:
            if not self._scope.is_responsible_for_plugin(plugin_type):
                continue

            plugin = self._scope.create_plugin(
                plugin_type,
                TrinityBootInfo(args, trinity_config, boot_kwargs)
            )
            plugin.ready(self.event_bus_endpoint)

            self._plugin_store.append(plugin)

    def shutdown_blocking(self) -> None:
        """
        Synchronously shut down all running plugins. Raises an
        :class:`~trinity.extensibility.exceptions.UnsuitableShutdownError` if called on a
        :class:`~trinity.extensibility.plugin_manager.PluginManager` that operates in the
        :class:`~trinity.extensibility.plugin_manager.SharedProcessScope`.
        """

        if isinstance(self._scope, SharedProcessScope):
            raise UnsuitableShutdownError("Use `shutdown` for instances of this scope")

        self._logger.info("Shutting down PluginManager with scope %s", type(self._scope))

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

    async def shutdown(self) -> None:
        """
        Asynchronously shut down all running plugins. Raises an
        :class:`~trinity.extensibility.exceptions.UnsuitableShutdownError` if called on a
        :class:`~trinity.extensibility.plugin_manager.PluginManager` that operates in the
        :class:`~trinity.extensibility.plugin_manager.MainAndIsolatedProcessScope`.
        """
        if isinstance(self._scope, MainAndIsolatedProcessScope):
            raise UnsuitableShutdownError("Use `shutdown_blocking` for instances of this scope")

        self._logger.info("Shutting down PluginManager with scope %s", type(self._scope))

        async_plugins = [
            plugin for plugin in self._plugin_store
            if isinstance(plugin, BaseAsyncStopPlugin) and plugin.running
        ]

        stop_results = await asyncio.gather(
            *self._stop_plugins(async_plugins), return_exceptions=True
        )

        for plugin, result in zip(async_plugins, stop_results):
            if isinstance(result, Exception):
                self._logger.error(
                    'Exception thrown while stopping plugin %s: %s', plugin.name, result
                )
            else:
                self._logger.info("Successfully stopped plugin: %s", plugin.name)

    def _stop_plugins(self,
                      plugins: Iterable[BaseAsyncStopPlugin]
                      ) -> Iterable[Awaitable[Optional[Exception]]]:
        for plugin in plugins:
            self._logger.info("Stopping plugin: %s", plugin.name)
            yield plugin.stop()
