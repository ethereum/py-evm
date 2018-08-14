from abc import ABC, abstractmethod
import asyncio
import functools
import logging
from typing import (
    Any,
    Awaitable,
    Callable,
    List,
    Optional,
    cast,
)
from weakref import WeakSet

from eth.tools.logging import TraceLogger

from cancel_token import CancelToken, OperationCancelled

from p2p.cancellable import CancellableMixin
from p2p.utils import get_asyncio_executor


class ServiceEvents:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.stopped = asyncio.Event()
        self.cleaned_up = asyncio.Event()
        self.cancelled = asyncio.Event()
        self.finished = asyncio.Event()


class BaseService(ABC, CancellableMixin):
    logger: TraceLogger = None
    _child_services: List['BaseService']
    # Use a WeakSet so that we don't have to bother updating it when tasks finish.
    _tasks: 'WeakSet[asyncio.Future[Any]]'
    _finished_callbacks: List[Callable[['BaseService'], None]]
    # Number of seconds cancel() will wait for run() to finish.
    _wait_until_finished_timeout = 5

    # the custom event loop to run in, or None if the default loop should be used
    _loop: asyncio.AbstractEventLoop = None

    _logger: TraceLogger = None

    def __init__(self,
                 token: CancelToken=None,
                 loop: asyncio.AbstractEventLoop = None) -> None:
        self.events = ServiceEvents()
        self._run_lock = asyncio.Lock()
        self._child_services = []
        self._tasks = WeakSet()
        self._finished_callbacks = []

        self._loop = loop

        base_token = CancelToken(type(self).__name__, loop=loop)

        if token is None:
            self.cancel_token = base_token
        else:
            self.cancel_token = base_token.chain(token)

        self._executor = get_asyncio_executor()

    @property
    def logger(self) -> TraceLogger:
        if self._logger is None:
            self._logger = cast(
                TraceLogger,
                logging.getLogger(self.__module__ + '.' + self.__class__.__name__)
            )
        return self._logger

    def get_event_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            return asyncio.get_event_loop()
        else:
            return self._loop

    async def run(
            self,
            finished_callback: Optional[Callable[['BaseService'], None]] = None) -> None:
        """Await for the service's _run() coroutine.

        Once _run() returns, triggers the cancel token, call cleanup() and
        finished_callback (if one was passed).
        """
        if self.is_running:
            raise RuntimeError("Cannot start the service while it's already running")
        elif self.cancel_token.triggered:
            raise RuntimeError("Cannot restart a service that has already been cancelled")

        if finished_callback:
            self._finished_callbacks.append(finished_callback)

        try:
            async with self._run_lock:
                self.events.started.set()
                await self._run()
        except OperationCancelled as e:
            self.logger.debug("%s finished: %s", self, e)
        except Exception:
            self.logger.exception("Unexpected error in %r, exiting", self)
        finally:
            # Trigger our cancel token to ensure all pending asyncio tasks and background
            # coroutines started by this service exit cleanly.
            self.events.cancelled.set()
            self.cancel_token.trigger()

            await self.cleanup()

            for callback in self._finished_callbacks:
                callback(self)

            self.events.finished.set()
            self.logger.debug("%s halted cleanly", self)

    def add_finished_callback(self, finished_callback: Callable[['BaseService'], None]) -> None:
        self._finished_callbacks.append(finished_callback)

    def run_task(self, awaitable: Awaitable[Any]) -> None:
        """Run the given awaitable in the background.

        The awaitable should return whenever this service's cancel token is triggered.

        If it raises OperationCancelled, that is caught and ignored.
        """
        async def f() -> None:
            try:
                await awaitable
            except OperationCancelled:
                pass
        self._tasks.add(asyncio.ensure_future(f()))

    def run_child_service(self, child_service: 'BaseService') -> None:
        """
        Run a child service and keep a reference to it to be considered during the cleanup.
        """
        self._child_services.append(child_service)
        self.run_task(child_service.run())

    async def _run_in_executor(self, callback: Callable[..., Any], *args: Any) -> Any:
        loop = self.get_event_loop()
        return await self.wait(loop.run_in_executor(self._executor, callback, *args))

    async def cleanup(self) -> None:
        """
        Run the ``_cleanup()`` coroutine and set the ``cleaned_up`` event after the service as
        well as all child services finished their cleanup.

        The ``_cleanup()`` coroutine is invoked before the child services may have finished
        their cleanup.
        """
        await asyncio.gather(*[
            child_service.events.cleaned_up.wait()
            for child_service in self._child_services],
            *[task for task in self._tasks],
            self._cleanup()
        )

        self.events.cleaned_up.set()

    async def cancel(self) -> None:
        """Trigger the CancelToken and wait for the cleaned_up event to be set."""
        if self.cancel_token.triggered:
            self.logger.warning("Tried to cancel %s, but it was already cancelled", self)
            return
        elif not self.is_running:
            raise RuntimeError("Cannot cancel a service that has not been started")

        self.logger.debug("Cancelling %s", self)
        self.events.cancelled.set()
        self.cancel_token.trigger()
        try:
            await asyncio.wait_for(
                self.events.cleaned_up.wait(), timeout=self._wait_until_finished_timeout)
        except asyncio.futures.TimeoutError:
            self.logger.info(
                "Timed out waiting for %s to finish its cleanup, forcibly cancelling pending "
                "tasks and exiting anyway", self)
            self._forcibly_cancel_all_tasks()
            # Sleep a bit because the Future.cancel() method just schedules the callbacks, so we
            # need to give the event loop a chance to actually call them.
            await asyncio.sleep(0.5)
        else:
            self.logger.debug("%s finished cleanly", self)

    def _forcibly_cancel_all_tasks(self) -> None:
        for task in self._tasks:
            task.cancel()

    @property
    def is_running(self) -> bool:
        return self._run_lock.locked()

    async def threadsafe_cancel(self) -> None:
        """
        Cancel service in another thread. Block until service is cleaned up.

        :param poll_period: how many seconds to wait in between each check for service cleanup
        """
        asyncio.run_coroutine_threadsafe(self.cancel(), loop=self.get_event_loop())
        await asyncio.wait_for(
            self.events.cleaned_up.wait(),
            timeout=self._wait_until_finished_timeout,
        )

    async def sleep(self, delay: float) -> None:
        """Coroutine that completes after a given time (in seconds)."""
        await self.wait(asyncio.sleep(delay))

    @abstractmethod
    async def _run(self) -> None:
        """Run the service's loop.

        Should return or raise OperationCancelled when the CancelToken is triggered.
        """
        raise NotImplementedError()

    async def _cleanup(self) -> None:
        """Clean up any resources held by this service.

        Called after the service's _run() method returns.
        """
        pass


def service_timeout(timeout: int) -> Callable[..., Any]:
    """
    Decorator to time out a method call.

    :param timeout: seconds to wait before raising a timeout exception

    :raise asyncio.futures.TimeoutError: if the call is not complete before timeout seconds
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapped(service: BaseService, *args: Any, **kwargs: Any) -> Any:
            return await service.wait(
                func(service, *args, **kwargs),
                timeout=timeout,
            )
        return wrapped
    return decorator


class EmptyService(BaseService):
    async def _run(self) -> None:
        pass

    async def _cleanup(self) -> None:
        pass
