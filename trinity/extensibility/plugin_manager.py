from argparse import (
    ArgumentParser,
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

from trinity.extensibility.events import (
    BaseEvent,
    PluginStartedEvent,
)
from trinity.extensibility.plugin import (
    BasePlugin,
    PluginContext,
    PluginProcessScope,
)


class MainAndOwnProcessScope():

    def __init__(self, event_bus: EventBus, main_proc_endpoint: Endpoint) -> None:
        self.event_bus = event_bus
        self.endpoint = main_proc_endpoint


class SharedProcessScope():

    def __init__(self, shared_proc_endpoint: Endpoint) -> None:
        self.endpoint = shared_proc_endpoint


ManagerProcessScope = Union[SharedProcessScope, MainAndOwnProcessScope]


class PluginManager:
    """
    The plugin manager is responsible to register, keep and manage the life cycle of any available
    plugins.

      .. note::

        This API is very much in flux and is expected to change heavily.
    """

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

            context = self._create_context_for_plugin(plugin)
            plugin.start(context)
            self._started_plugins.append(plugin)
            self._logger.info("Plugin started: {}".format(plugin.name))
            self.broadcast(PluginStartedEvent(plugin), plugin)

    # FIXME: This is a temporary API
    def start(self, boot_kwargs: Dict[str, Any]) -> None:
        for plugin in self._plugin_store:

            # This whole API is going away so for now, we aren't caring about
            # any of the other plugins

            if plugin.process_scope is not PluginProcessScope.OWN:
                continue

            context = self._create_context_for_plugin(plugin, boot_kwargs)
            plugin.start(context)

    def _is_responsible_for_plugin(self, plugin: BasePlugin) -> bool:

        main_and_own_scopes = [PluginProcessScope.MAIN, PluginProcessScope.OWN]
        plugin_for_main_or_own = plugin.process_scope in main_and_own_scopes
        plugin_for_shared = not plugin_for_main_or_own

        manager_for_main_or_own = isinstance(self._scope, MainAndOwnProcessScope)
        manager_for_shared = not manager_for_main_or_own

        return (plugin_for_main_or_own and manager_for_main_or_own or
                plugin_for_shared and manager_for_shared)

    def _create_context_for_plugin(self,
                                   plugin: BasePlugin,
                                   boot_kwargs: Dict[str, Any] = None) -> PluginContext:

        if plugin.process_scope is PluginProcessScope.SHARED:
            # A plugin that runs in a shared process gets the endpoint of the PluginManager
            # injected to communicate with the rest of the world
            return PluginContext(self._scope.endpoint)
        elif plugin.process_scope is PluginProcessScope.OWN:
            # A plugin that runs in it's own process gets a new endpoint created to get
            # passed into that new process

            # mypy doesn't know it can only be that scope at this point. The `isinstance`
            # check avoids adding an ignore
            if isinstance(self._scope, MainAndOwnProcessScope):
                endpoint = self._scope.event_bus.create_endpoint(plugin.name)
                return PluginContext(endpoint, boot_kwargs)

        raise Exception("Invariant: unreachable code path")
