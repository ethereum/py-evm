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
    Dict,
    Iterable,
    List,
    Optional,
    Union,
)

from lahja import (
    Endpoint,
    EventBus,
)

from trinity.config import (
    ChainConfig
)
from trinity.extensibility.events import (
    BaseEvent,
    PluginStartedEvent,
)
from trinity.extensibility.exceptions import (
    UnsuitableShutdownError,
)
from trinity.extensibility.plugin import (
    BaseAsyncStopPlugin,
    BaseIsolatedPlugin,
    BaseMainProcessPlugin,
    BasePlugin,
    BaseSyncStopPlugin,
    PluginContext,
)


class BaseManagerProcessScope(ABC):
    """
    Define the operational model under which a ``PluginManager`` runs.
    """

    endpoint: Endpoint

    @abstractmethod
    def is_responsible_for_plugin(self, plugin: BasePlugin) -> bool:
        """
        Define whether a ``PluginManager`` operating under this scope is responsible
        for a given plugin or not.
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @abstractmethod
    def create_plugin_context(self,
                              plugin: BasePlugin,
                              args: Namespace,
                              chain_config: ChainConfig,
                              boot_kwargs: Dict[str, Any]) -> PluginContext:
        """
        Create the ``PluginContext`` for a given plugin.
        """
        raise NotImplementedError("Must be implemented by subclasses")


class MainAndIsolatedProcessScope(BaseManagerProcessScope):

    def __init__(self, event_bus: EventBus, main_proc_endpoint: Endpoint) -> None:
        self.event_bus = event_bus
        self.endpoint = main_proc_endpoint

    def is_responsible_for_plugin(self, plugin: BasePlugin) -> bool:
        return isinstance(plugin, BaseIsolatedPlugin) or isinstance(plugin, BaseMainProcessPlugin)

    def create_plugin_context(self,
                              plugin: BasePlugin,
                              args: Namespace,
                              chain_config: ChainConfig,
                              boot_kwargs: Dict[str, Any]) -> PluginContext:

        if isinstance(plugin, BaseIsolatedPlugin):
            # Isolated plugins get an entirely new endpoint to be passed into that new process
            context = PluginContext(
                self.event_bus.create_endpoint(plugin.name)
            )
            context.args = args
            context.chain_config = chain_config
            context.boot_kwargs = boot_kwargs
            return context

        # A plugin that overtakes the main process never gets far enough to even get a context.
        # For now it should be safe to just return `None`. Maybe reconsider in the future.
        return None


class SharedProcessScope(BaseManagerProcessScope):

    def __init__(self, shared_proc_endpoint: Endpoint) -> None:
        self.endpoint = shared_proc_endpoint

    def is_responsible_for_plugin(self, plugin: BasePlugin) -> bool:
        return isinstance(plugin, BaseAsyncStopPlugin)

    def create_plugin_context(self,
                              plugin: BasePlugin,
                              args: Namespace,
                              chain_config: ChainConfig,
                              boot_kwargs: Dict[str, Any]) -> PluginContext:

        # Plugins that run in a shared process all share the endpoint of the plugin manager
        context = PluginContext(self.endpoint)
        context.args = args
        context.chain_config = chain_config
        context.boot_kwargs = boot_kwargs
        return context


class PluginManager:
    """
    The plugin manager is responsible to register, keep and manage the life cycle of any available
    plugins.

      .. note::

        This API is very much in flux and is expected to change heavily.
    """

    def __init__(self, scope: BaseManagerProcessScope) -> None:
        self._scope = scope
        self._plugin_store: List[BasePlugin] = []
        self._started_plugins: List[BasePlugin] = []
        self._logger = logging.getLogger("trinity.extensibility.plugin_manager.PluginManager")

    @property
    def event_bus_endpoint(self) -> Endpoint:
        """
        Return the ``Endpoint`` that the ``PluginManager`` uses to connect to the ``EventBus``
        """
        return self._scope.endpoint

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

            if plugin is exclude or not self._scope.is_responsible_for_plugin(plugin):
                self._logger.debug("Skipping plugin %s (not responsible)", plugin.name)
                continue

            plugin.handle_event(event)

            if plugin in self._started_plugins:
                continue

            if not plugin.should_start():
                continue

            plugin._start()
            self._started_plugins.append(plugin)
            self._logger.info("Plugin started: %s", plugin.name)
            self.broadcast(PluginStartedEvent(plugin), plugin)

    def prepare(self,
                args: Namespace,
                chain_config: ChainConfig,
                boot_kwargs: Dict[str, Any] = None) -> None:
        """
        Create a ``PluginContext`` for every plugin that this plugin manager instance
        is responsible for.
        """
        for plugin in self._plugin_store:

            if not self._scope.is_responsible_for_plugin(plugin):
                continue

            context = self._scope.create_plugin_context(plugin, args, chain_config, boot_kwargs)
            plugin.set_context(context)

    def shutdown_blocking(self) -> None:
        """
        Synchronously shut down all started plugins.
        """

        if isinstance(self._scope, SharedProcessScope):
            raise UnsuitableShutdownError("Use `shutdown` for instances of this scope")

        self._logger.info("Shutting down PluginManager with scope %s", type(self._scope))

        for plugin in self._started_plugins:

            if not isinstance(plugin, BaseSyncStopPlugin):
                continue

            try:
                self._logger.info("Stopping plugin: %s", plugin.name)
                plugin.stop()
                self._logger.info("Successfully stopped plugin: %s", plugin.name)
            except Exception:
                self._logger.exception("Exception thrown while stopping plugin %s", plugin.name)

    async def shutdown(self) -> None:
        """
        Asynchronously shut down all started plugins.
        """

        if isinstance(self._scope, MainAndIsolatedProcessScope):
            raise UnsuitableShutdownError("Use `shutdown_blocking` for instances of this scope")

        self._logger.info("Shutting down PluginManager with scope %s", type(self._scope))

        async_plugins = [
            plugin for plugin in self._started_plugins
            if isinstance(plugin, BaseAsyncStopPlugin)
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
