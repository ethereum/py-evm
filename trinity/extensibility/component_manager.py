import logging
from typing import (
    Iterable,
    List,
    Type,
)

from lahja import EndpointAPI

from trinity.boot_info import BootInfo
from trinity.extensibility.component import (
    BaseIsolatedComponent,
    BaseComponent,
)
from trinity._utils.ipc import (
    kill_processes_gracefully,
)


class ComponentManager:
    """
    The component manager is responsible for managing the life cycle of any available
    components.

    A :class:`~trinity.extensibility.component_manager.ComponentManager` is tight to a specific
    :class:`~trinity.extensibility.component_manager.BaseManagerProcessScope` which defines which
    components are controlled by this specific manager instance.

    This is due to the fact that Trinity currently allows components to either run in a shared
    process, also known as the "networking" process, as well as in their own isolated
    processes.

    Trinity uses two different :class:`~trinity.extensibility.component_manager.ComponentManager`
    instances to govern these different categories of components.

      .. note::

        This API is very much in flux and is expected to change heavily.
    """

    def __init__(self,
                 endpoint: EndpointAPI,
                 components: Iterable[Type[BaseComponent]]) -> None:
        self._endpoint = endpoint
        self._registered_components: List[Type[BaseComponent]] = list(components)
        self._component_store: List[BaseComponent] = []
        self._logger = logging.getLogger("trinity.extensibility.component_manager.ComponentManager")

    @property
    def event_bus_endpoint(self) -> EndpointAPI:
        """
        Return the :class:`~lahja.endpoint.Endpoint` that the
        :class:`~trinity.extensibility.component_manager.ComponentManager` instance uses to connect
        to the event bus.
        """
        return self._endpoint

    def prepare(self, boot_info: BootInfo) -> None:
        """
        Create all components and call :meth:`~trinity.extensibility.component.BaseComponent.ready`
        on each of them.
        """
        for component_type in self._registered_components:

            component = component_type(boot_info)
            component.ready(self.event_bus_endpoint)

            self._component_store.append(component)

    def shutdown_blocking(self) -> None:
        """
        Synchronously shut down all running components.
        """

        self._logger.info("Shutting down ComponentManager")

        components = [
            component for component in self._component_store
            if isinstance(component, BaseIsolatedComponent) and component.running
        ]
        processes = [component.process for component in components]

        for component in components:
            self._logger.info("Stopping component: %s", component.name)

        kill_processes_gracefully(processes, self._logger)

        for component in components:
            self._logger.info("Successfully stopped component: %s", component.name)
