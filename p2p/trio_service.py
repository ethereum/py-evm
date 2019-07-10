from abc import ABC, abstractmethod
import logging
import sys
from types import TracebackType
from typing import Any, Callable, Awaitable, Optional, Tuple, Type, AsyncIterator

from async_generator import asynccontextmanager

import trio

import trio_typing


class ManagerAPI(ABC):
    @property
    @abstractmethod
    def has_started(self) -> bool:
        ...

    @property
    @abstractmethod
    def is_running(self) -> bool:
        ...

    @property
    @abstractmethod
    def is_cancelled(self) -> bool:
        ...

    @property
    @abstractmethod
    def is_stopped(self) -> bool:
        ...

    @property
    @abstractmethod
    def did_error(self) -> bool:
        ...

    @abstractmethod
    def cancel(self) -> None:
        ...

    @abstractmethod
    async def wait_started(self) -> None:
        ...

    @abstractmethod
    async def wait_cancelled(self) -> None:
        ...

    @abstractmethod
    async def wait_stopped(self) -> None:
        ...

    @abstractmethod
    async def _run_daemon_task(self,
                               coro: Callable[..., Awaitable[Any]],
                               *args: Any,
                               name: str = None) -> None:
        ...


LogicFnType = Callable[[ManagerAPI], Awaitable[Any]]


class Service(ABC):
    async def start(self, nursery: trio_typing.Nursery) -> 'ServiceManager':
        manager = ServiceManager(self)
        nursery.start_soon(manager.run)
        return manager

    @abstractmethod
    async def run(self, manager: ManagerAPI) -> None:
        ...


def as_service(logic_fn: LogicFnType) -> Type[Service]:
    """
    Create a service out of a simple function
    """
    class _Service(Service):
        def __init__(self, *args: Any, **kwargs: Any):
            self._args = args
            self._kwargs = kwargs

        async def run(self, manager: ManagerAPI) -> None:
            await logic_fn(manager, *self._args, **self._kwargs)  # type: ignore

    _Service.__name__ = logic_fn.__name__
    _Service.__doc__ = logic_fn.__doc__
    return _Service


class ServiceManager(ManagerAPI):
    logger = logging.getLogger('p2p.trio_service.ServiceManager')

    _run_error: Optional[Tuple[
        Optional[Type[BaseException]],
        Optional[BaseException],
        Optional[TracebackType],
    ]] = None

    def __init__(self, logic: Service) -> None:
        self.logic = logic

        # events
        self._started = trio.Event()
        self._cancelled = trio.Event()
        self._stopped = trio.Event()

        # locks
        self._run_lock = trio.Lock()

    async def _handle_cancelled(self, nursery: trio_typing.Nursery) -> None:
        """
        Handles the case where cancellation occurs because the
        `event.set_cancelled()` has been called, this propagates that to force
        the nursery to be cancelled.
        """
        self.logger.debug('%s: _handle_cancelled waiting for cancellation', self)
        await self._cancelled.wait()
        self.logger.debug('%s: _handle_cancelled triggering nursery cancellation', self)
        nursery.cancel_scope.cancel()

    async def _handle_run(self) -> None:
        """
        Triggers cancellation in the case where the service exits normally or
        throws an exception.
        """
        self._started.set()
        try:
            await self.logic.run(self)
        except Exception as err:
            self.logger.debug(
                '%s: _handle_run got error, storing exception and setting cancelled',
                self
            )
            self.logger.exception('GOT THIS')
            self._run_error = sys.exc_info()
        finally:
            self.logger.debug('%s: _handle_run triggering service cancellation', self)
            self.cancel()

    async def run(self) -> None:
        if self._run_lock.locked():
            raise Exception("TODO: run lock already engaged")
        elif self.has_started:
            raise Exception("TODO: already started. No reentrance")

        async with self._run_lock:

            # Open a nursery
            async with trio.open_nursery() as nursery:
                self._nursery = nursery

                nursery.start_soon(self._handle_cancelled, nursery)
                nursery.start_soon(self._handle_run)

                # This wait is not strictly necessary as this context block
                # will not exit until the background tasks have completed.
                await self.wait_cancelled()

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
    def has_started(self) -> bool:
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
        if not self.has_started:
            raise Exception("TODO: never started")
        self._cancelled.set()

    #
    # Wait API
    #
    async def wait_started(self) -> None:
        await self._started.wait()

    async def wait_cancelled(self) -> None:
        await self._cancelled.wait()

    async def wait_stopped(self) -> None:
        await self._stopped.wait()

    async def _run_daemon_task(self,
                               coro: Callable[..., Awaitable[Any]],
                               *args: Any,
                               name: str = None) -> None:
        try:
            await coro(*args)
        except Exception as err:
            self.logger.debug(
                "Daemon task '%s' exited with error: %s",
                name or coro,
                err,
                exc_info=True,
            )
        else:
            self.logger.debug(
                "Daemon task '%s' exited.",
                name or coro,
            )
        finally:
            self.cancel()

    def run_daemon_task(self,
                        coro: Callable[[Any], Awaitable[Any]],
                        *args: Any,
                        name: str = None) -> None:
        self._nursery.start_soon(
            self._run_daemon_task,
            coro,
            *args,
        )


@asynccontextmanager
async def run_service(service: Service) -> AsyncIterator[ManagerAPI]:
    async with trio.open_nursery() as nursery:
        manager = await service.start(nursery)
        try:
            yield manager
        finally:
            manager.cancel()
            await manager.wait_stopped()
