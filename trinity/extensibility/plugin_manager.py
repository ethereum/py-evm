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
from trinity.extensibility.plugin import (
    BasePlugin,
    PluginContext,
    PluginProcessScope,
)


class MainAndIsolatedProcessScope():

    def __init__(self, event_bus: EventBus, main_proc_endpoint: Endpoint) -> None:
        self.event_bus = event_bus
        self.endpoint = main_proc_endpoint


class SharedProcessScope():

    def __init__(self, shared_proc_endpoint: Endpoint) -> None:
        self.endpoint = shared_proc_endpoint


ManagerProcessScope = Union[SharedProcessScope, MainAndIsolatedProcessScope]


class PluginManager:
    """
    The plugin manager is responsible to register, keep and manage the life cycle of any available
    plugins.

      .. note::

        This API is very much in flux and is expected to change heavily.
    """

    MAIN_AND_ISOLATED_SCOPES = {PluginProcessScope.MAIN, PluginProcessScope.ISOLATED}
    MAIN_AND_SHARED_SCOPES = {PluginProcessScope.MAIN, PluginProcessScope.SHARED}

    def __init__(self, scope: ManagerProcessScope) -> None:
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

            if plugin is exclude or not self._is_responsible_for_plugin(plugin):
                continue

            plugin.handle_event(event)

            if plugin in self._started_plugins:
                continue

            if not plugin.should_start():
                continue

            plugin._start()
            self._started_plugins.append(plugin)
            self._logger.info("Plugin started: {}".format(plugin.name))
            self.broadcast(PluginStartedEvent(plugin), plugin)

    def prepare(self,
                args: Namespace,
                chain_config: ChainConfig,
                boot_kwargs: Dict[str, Any] = None) -> None:
        for plugin in self._plugin_store:

            if not self._is_responsible_for_plugin(plugin):
                continue

            context = self._create_context_for_plugin(plugin, args, chain_config, boot_kwargs)
            plugin.set_context(context)

    def shutdown(self) -> None:
        for plugin in self._started_plugins:
            try:
                plugin.stop()
            except Exception:
                self._logger.exception("Exception thrown while stopping plugin %s", plugin.name)

    def _is_responsible_for_plugin(self, plugin: BasePlugin) -> bool:

        main_or_isolated_plugin = plugin.process_scope in self.MAIN_AND_ISOLATED_SCOPES
        shared_plugin = not main_or_isolated_plugin

        manager_for_main_or_isolated = isinstance(self._scope, MainAndIsolatedProcessScope)
        manager_for_shared = not manager_for_main_or_isolated

        return ((main_or_isolated_plugin and manager_for_main_or_isolated) or
                (shared_plugin and manager_for_shared))

    def _create_context_for_plugin(self,
                                   plugin: BasePlugin,
                                   args: Namespace,
                                   chain_config: ChainConfig,
                                   boot_kwargs: Dict[str, Any]) -> PluginContext:

        context: PluginContext = None
        if plugin.process_scope in self.MAIN_AND_SHARED_SCOPES:
            # A plugin that runs in a shared process as well as a plugin that overtakes the main
            # process uses the endpoint of the PluginManager which will either be the main
            # endpoint or the networking endpoint in the case of Trinity
            context = PluginContext(self._scope.endpoint)
        elif plugin.process_scope is PluginProcessScope.ISOLATED:
            # A plugin that runs in it's own process gets a new endpoint created to get
            # passed into that new process

            # mypy doesn't know it can only be that scope at this point. The `isinstance`
            # check avoids adding an ignore
            if isinstance(self._scope, MainAndIsolatedProcessScope):
                endpoint = self._scope.event_bus.create_endpoint(plugin.name)
                context = PluginContext(endpoint)
        else:
            Exception("Invariant: unreachable code path")

        context.args = args
        context.chain_config = chain_config
        context.boot_kwargs = boot_kwargs

        return context
