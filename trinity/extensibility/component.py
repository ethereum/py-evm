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
from multiprocessing import (
    Process
)

from lahja.base import EndpointAPI

from trinity.extensibility.events import (
    ComponentStartedEvent,
)
from trinity.extensibility.exceptions import (
    InvalidComponentStatus,
)
from trinity._utils.mp import (
    ctx,
)
from trinity._utils.logging import (
    setup_child_process_logging,
)
from trinity._utils.os import (
    friendly_filename_or_url,
)
from trinity._utils.profiling import (
    profiler,
)
from trinity.boot_info import BootInfo


class ComponentStatus(Enum):
    NOT_READY = auto()
    READY = auto()
    STARTED = auto()
    STOPPED = auto()


INVALID_START_STATUS = (ComponentStatus.NOT_READY, ComponentStatus.STARTED,)


class BaseComponent(ABC):

    _status: ComponentStatus = ComponentStatus.NOT_READY

    def __init__(self, boot_info: BootInfo) -> None:
        self.boot_info = boot_info

    @property
    @abstractmethod
    def event_bus(self) -> EndpointAPI:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Describe the name of the component.
        """
        ...

    @property
    def normalized_name(self) -> str:
        """
        The normalized (computer readable) name of the component
        """
        return friendly_filename_or_url(self.name)

    @classmethod
    def get_logger(cls) -> logging.Logger:
        return logging.getLogger(f'trinity.extensibility.component(#{cls.__name__})')

    @property
    def logger(self) -> logging.Logger:
        return self.get_logger()

    @property
    def running(self) -> bool:
        """
        Return ``True`` if the ``status`` is ``ComponentStatus.STARTED``,
        otherwise return ``False``.
        """
        return self._status is ComponentStatus.STARTED

    @property
    def status(self) -> ComponentStatus:
        """
        Return the current :class:`~trinity.extensibility.component.ComponentStatus`
        of the component.
        """
        return self._status

    def ready(self, manager_eventbus: EndpointAPI) -> None:
        """
        Set the ``status`` to ``ComponentStatus.READY`` and delegate to
        :meth:`~trinity.extensibility.component.BaseComponent.on_ready`
        """
        self._status = ComponentStatus.READY
        self.on_ready(manager_eventbus)

    def on_ready(self, manager_eventbus: EndpointAPI) -> None:
        """
        Notify the component that it is ready to bootstrap itself.
        The ``manager_eventbus`` refers to the instance of the
        :class:`~lahja.endpoint.Endpoint` that the
        :class:`~trinity.extensibility.component_manager.ComponentManager` uses which may or may not
        be the same :class:`~lahja.endpoint.Endpoint` as the component uses depending on the type
        of the component. The component should use this :class:`~lahja.endpoint.Endpoint` instance
        to listen for events *before* the component has started.
        """
        pass

    @classmethod
    def configure_parser(cls, arg_parser: ArgumentParser, subparser: _SubParsersAction) -> None:
        """
        Give the component a chance to amend the Trinity CLI argument parser. This hook is called
        before :meth:`~trinity.extensibility.component.BaseComponent.on_ready`
        """
        pass

    def start(self) -> None:
        """
        Delegate to :meth:`~trinity.extensibility.component.BaseComponent.do_start` and set
        ``running`` to ``True``. Broadcast a
        :class:`~trinity.extensibility.events.ComponentStartedEvent` on the event bus and hence
        allow other components to act accordingly.
        """

        if self._status in INVALID_START_STATUS:
            raise InvalidComponentStatus(
                f"Can not start component when the component status is {self.status}"
            )

        self._status = ComponentStatus.STARTED
        self.do_start()
        self.event_bus.broadcast_nowait(
            ComponentStartedEvent(type(self))
        )
        self.logger.info("Component started: %s", self.name)

    def do_start(self) -> None:
        """
        Perform the actual component start routine. In the case of a `BaseIsolatedComponent` this
        method will be called in a separate process.

        This method should usually be overwritten by subclasses with the exception of components
        that set ``func`` on the ``ArgumentParser`` to redefine the entire host program.
        """
        pass


class BaseMainProcessComponent(BaseComponent):
    """
    A :class:`~trinity.extensibility.component.BaseMainProcessComponent` overtakes the whole main
    process early before any of the subsystems started. In that sense it redefines the whole meaning
    of the ``trinity`` command.
    """

    @property
    def event_bus(self) -> EndpointAPI:
        raise NotImplementedError('BaseMainProcessComponents do not have event busses')


class BaseIsolatedComponent(BaseComponent):
    """
    A :class:`~trinity.extensibility.component.BaseIsolatedComponent` runs in an isolated process
    and hence provides security and flexibility by not making assumptions about its internal
    operations.

    Such components are free to use non-blocking asyncio as well as synchronous calls. When an
    isolated component is stopped it does first receive a SIGINT followed by a SIGTERM soon after.
    It is up to the component to handle these signals accordingly.
    """
    _process: Process = None
    _event_bus: EndpointAPI = None

    @property
    def process(self) -> Process:
        """
        Return the ``Process`` created by the isolated component.
        """
        return self._process

    def start(self) -> None:
        """
        Prepare the component to get started and eventually call ``do_start`` in a separate process.
        """
        self._status = ComponentStatus.STARTED
        self._process = ctx.Process(
            target=self._prepare_spawn,
        )

        self._process.start()
        self.logger.info("Component started: %s (pid=%d)", self.name, self._process.pid)

    def _prepare_spawn(self) -> None:
        if self.boot_info.profile:
            with profiler(f'profile_{self.normalized_name}'):
                self._spawn_start()
        else:
            self._spawn_start()

    @abstractmethod
    def _spawn_start(self) -> None:
        ...

    def stop(self) -> None:
        """
        Set the ``status`` to `STOPPED`` but rely on the
        :class:`~trinity.extensibility.component_manager.ComponentManager` to tear down the process.
        This allows isolated components to be taken down concurrently without depending on a running
        event loop.
        """
        self._status = ComponentStatus.STOPPED

    def _setup_logging(self) -> None:
        setup_child_process_logging(self.boot_info)
