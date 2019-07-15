from abc import ABC, abstractmethod
import functools
import logging
import sys
from types import TracebackType
from typing import Any, Callable, Awaitable, Optional, Tuple, Type, AsyncIterator

from mypy_extensions import VarArg, KwArg

from async_generator import asynccontextmanager

import trio

import trio_typing


class ServiceException(Exception):
    """
    Base class for Service exceptions
    """
    pass


class LifecycleError(ServiceException):
    """
    Raised when an action would violate the service lifecycle rules.
    """
    pass


class ServiceAPI(ABC):
    manager: 'ManagerAPI'

    @abstractmethod
    async def run(self) -> None:
        """
        This method is where all of the Service class logic should be
        implemented.  It should **not** be invoked by user code but instead run
        with either:

        .. code-block: python

            # 1. run the service in the background using a context manager
            async with run_service(service) as manager:
                # service runs inside context block
                ...
                # service cancels and stops when context exits
            # service will have fully stopped

            # 2. run the service blocking until completion
            await Manager.run_service(service)

            # 3. create manager and then run service blocking until completion
            manager = Manager(service)
            await manager.run()
        """
        ...


class ManagerAPI(ABC):
    @property
    @abstractmethod
    def is_started(self) -> bool:
        """
        Return boolean indicating if the underlying service has been started.
        """
        ...

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """
        Return boolean indicating if the underlying service is actively
        running.  A service is considered running if it has been started and
        has not yet been stopped.
        """
        ...

    @property
    @abstractmethod
    def is_cancelled(self) -> bool:
        """
        Return boolean indicating if the underlying service has been cancelled.
        This can occure externally via the `cancel()` method or internally due
        to a task crash or a crash of the actual :meth:`ServiceAPI.run` method.
        """
        ...

    @property
    @abstractmethod
    def is_stopped(self) -> bool:
        """
        Return boolean indicating if the underlying service is stopped.  A
        stopped service will have completed all of the background tasks.
        """
        ...

    @property
    @abstractmethod
    def did_error(self) -> bool:
        """
        Return boolean indicating if the underlying service threw an exception.
        """
        ...

    @abstractmethod
    def cancel(self) -> None:
        """
        Trigger cancellation of the service.
        """
        ...

    @abstractmethod
    async def stop(self) -> None:
        """
        Trigger cancellation of the service and wait for it to stop.
        """
        ...

    @abstractmethod
    async def wait_started(self) -> None:
        """
        Wait until the service is started.
        """
        ...

    @abstractmethod
    async def wait_cancelled(self) -> None:
        """
        Wait until the service is cancelled.
        """
        ...

    @abstractmethod
    async def wait_stopped(self) -> None:
        """
        Wait until the service is stopped.
        """
        ...

    @classmethod
    @abstractmethod
    async def run_service(cls, service: ServiceAPI) -> None:
        """
        Run a service
        """
        ...

    @abstractmethod
    async def run(self) -> None:
        """
        Run a service
        """
        ...

    @trio_typing.takes_callable_and_args
    @abstractmethod
    async def run_task(self,
                       async_fn: Callable[[VarArg()], Awaitable[Any]],
                       *args: Any,
                       daemon: bool = False,
                       name: str = None) -> None:
        """
        Run a task in the background.  If the function throws an exception it
        will trigger the service to be cancelled and be propogated.

        If `daemon == True` then the the task is expected to run indefinitely
        and will trigger cancellation if the task finishes.
        """
        ...


LogicFnType = Callable[[ManagerAPI, VarArg(), KwArg()], Awaitable[Any]]


class Service(ServiceAPI):
    pass


def as_service(service_fn: LogicFnType) -> Type[Service]:
    """
    Create a service out of a simple function
    """
    class _Service(Service):
        def __init__(self, *args: Any, **kwargs: Any):
            self._args = args
            self._kwargs = kwargs

        async def run(self) -> None:
            await service_fn(self.manager, *self._args, **self._kwargs)

    _Service.__name__ = service_fn.__name__
    _Service.__doc__ = service_fn.__doc__
    return _Service


class Manager(ManagerAPI):
    logger = logging.getLogger('p2p.trio_service.Manager')

    _service: ServiceAPI

    _run_error: Optional[Tuple[
        Optional[Type[BaseException]],
        Optional[BaseException],
        Optional[TracebackType],
    ]] = None

    # A nursery for system tasks.  This nursery is cancelled in the event that
    # the service is cancelled or exits.
    _system_nursery: trio_typing.Nursery

    # A nursery for sub tasks and services.  This nursery is cancelled if the
    # service is cancelled but allowed to exit normally if the service exits.
    _task_nursery: trio_typing.Nursery

    def __init__(self, service: ServiceAPI) -> None:
        if hasattr(service, 'manager'):
            raise LifecycleError("Service already has a manager.")
        else:
            service.manager = self

        self._service = service

        # events
        self._started = trio.Event()
        self._cancelled = trio.Event()
        self._stopped = trio.Event()

        # locks
        self._run_lock = trio.Lock()

    #
    # System Tasks
    #
    async def _handle_cancelled(self,
                                task_nursery: trio_typing.Nursery,
                                ) -> None:
        """
        Handles the cancellation triggering cancellation of the task nursery.
        """
        self.logger.debug('%s: _handle_cancelled waiting for cancellation', self)
        await self.wait_cancelled()
        self.logger.debug('%s: _handle_cancelled triggering task nursery cancellation', self)
        task_nursery.cancel_scope.cancel()

    async def _handle_stopped(self,
                              system_nursery: trio_typing.Nursery) -> None:
        """
        Once the `_stopped` event is set this triggers cancellation of the system nursery.
        """
        self.logger.debug('%s: _handle_stopped waiting for stopped', self)
        await self.wait_stopped()
        self.logger.debug('%s: _handle_stopped triggering system nursery cancellation', self)
        system_nursery.cancel_scope.cancel()

    async def _handle_run(self) -> None:
        """
        Run and monitor the actual :meth:`ServiceAPI.run` method.

        In the event that it throws an exception the service will be cancelled.

        Upon a clean exit
        Triggers cancellation in the case where the service exits normally or
        throws an exception.
        """
        try:
            await self._service.run()
        except Exception as err:
            self.logger.debug(
                '%s: _handle_run got error, storing exception and setting cancelled',
                self
            )
            self._run_error = sys.exc_info()
            self.cancel()
        else:
            # NOTE: Any service which uses daemon tasks will need to trigger
            # cancellation in order for the service to exit since this code
            # path does not trigger task cancellation.  It might make sense to
            # trigger cancellation if all of the running tasks are daemon
            # tasks.
            self.logger.debug(
                '%s: _handle_run exited cleanly, waiting for full stop...',
                self
            )

    @classmethod
    async def run_service(cls, service: ServiceAPI) -> None:
        manager = cls(service)
        await manager.run()

    async def run(self) -> None:
        if self._run_lock.locked():
            raise LifecycleError(
                "Cannot run a service with the run lock already engaged.  Already started?"
            )
        elif self.is_started:
            raise LifecycleError("Cannot run a service which is already started.")

        async with self._run_lock:
            async with trio.open_nursery() as system_nursery:
                async with trio.open_nursery() as task_nursery:
                    self._task_nursery = task_nursery

                    system_nursery.start_soon(
                        self._handle_cancelled,
                        task_nursery,
                    )
                    system_nursery.start_soon(
                        self._handle_stopped,
                        system_nursery,
                    )

                    task_nursery.start_soon(self._handle_run)

                    self._started.set()

                    # ***BLOCKING HERE***
                    # The code flow will block here until the background tasks have
                    # completed or cancellation occurs.

                # Mark as having stopped
                self._stopped.set()
        self.logger.debug('%s stopped', self)

        # If an error occured, re-raise it here
        if self.did_error:
            _, exc_value, exc_tb = self._run_error
            raise exc_value.with_traceback(exc_tb)

    #
    # Event API mirror
    #
    @property
    def is_started(self) -> bool:
        return self._started.is_set()

    @property
    def is_running(self) -> bool:
        return self._started.is_set() and not self._stopped.is_set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()

    @property
    def is_stopped(self) -> bool:
        return self._stopped.is_set()

    @property
    def did_error(self) -> bool:
        return self._run_error is not None

    #
    # Control API
    #
    def cancel(self) -> None:
        if not self.is_started:
            raise LifecycleError("Cannot cancel as service which was never started.")
        self._cancelled.set()

    async def stop(self) -> None:
        self.cancel()
        await self.wait_stopped()

    #
    # Wait API
    #
    async def wait_started(self) -> None:
        await self._started.wait()

    async def wait_cancelled(self) -> None:
        await self._cancelled.wait()

    async def wait_stopped(self) -> None:
        await self._stopped.wait()

    async def _run_and_manage_task(self,
                                   async_fn: Callable[..., Awaitable[Any]],
                                   *args: Any,
                                   daemon: bool,
                                   name: str) -> None:
        try:
            await async_fn(*args)
        except Exception as err:
            self.logger.debug(
                "task '%s[daemon=%s]' exited with error: %s",
                name,
                daemon,
                err,
                exc_info=True,
            )
        else:
            self.logger.debug(
                "task '%s[daemon=%s]' finished.",
                name,
                daemon,
            )
        finally:
            if daemon:
                self.cancel()

    def run_task(self,
                 async_fn: Callable[..., Awaitable[Any]],
                 *args: Any,
                 daemon: bool = False,
                 name: str = None) -> None:

        self._task_nursery.start_soon(
            functools.partial(
                self._run_and_manage_task,
                daemon=daemon,
                name=name or repr(async_fn),
            ),
            async_fn,
            *args,
            name=name,
        )


@asynccontextmanager
async def background_service(service: ServiceAPI) -> AsyncIterator[ManagerAPI]:
    """
    This is the primary API for running a service without explicitely managing
    its lifecycle with a nursery.  The service is running within the context
    block and will be properly cleaned up upon exiting the context block.
    """
    async with trio.open_nursery() as nursery:
        manager = Manager(service)
        nursery.start_soon(manager.run)
        await manager.wait_started()
        try:
            yield manager
        finally:
            await manager.stop()
