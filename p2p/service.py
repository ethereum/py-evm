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
    TypeVar
    cast,
)

from evm.utils.logging import TraceLogger

from p2p.cancel_token import CancellableMixin, CancelToken
from p2p.exceptions import OperationCancelled


class BaseService(ABC, CancellableMixin):
    logger: TraceLogger = None
    _child_services: List['BaseService'] = []
    # Number of seconds cancel() will wait for run() to finish.
    _wait_until_finished_timeout = 5

    def __init__(self, token: CancelToken=None) -> None:
        if self.logger is None:
            self.logger = cast(
                TraceLogger, logging.getLogger(self.__module__ + '.' + self.__class__.__name__))

        self._run_lock = asyncio.Lock()
        self.cleaned_up = asyncio.Event()

        base_token = CancelToken(type(self).__name__)
        if token is None:
            self.cancel_token = base_token
        else:
            self.cancel_token = base_token.chain(token)

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

        try:
            async with self._run_lock:
                await self._run()
        except OperationCancelled as e:
            self.logger.info("%s finished: %s", self, e)
        except Exception:
            self.logger.exception("Unexpected error in %r, exiting", self)
        finally:
            # Trigger our cancel token to ensure all pending asyncio tasks and background
            # coroutines started by this service exit cleanly.
            self.cancel_token.trigger()

            await self.cleanup()

            if finished_callback is not None:
                finished_callback(self)

    def run_child_service(self, child_service: 'BaseService') -> 'asyncio.Future[Any]':
        """
        Run a child service and keep a reference to it to be considered during the cleanup.
        """
        self._child_services.append(child_service)
        return asyncio.ensure_future(child_service.run())

    async def cleanup(self) -> None:
        """
        Run the ``_cleanup()`` coroutine and set the ``cleaned_up`` event after the service as
        well as all child services finished their cleanup.

        The ``_cleanup()`` coroutine is invoked before the child services may have finished
        their cleanup.
        """

        await asyncio.gather(*[
            child_service.cleaned_up.wait()
            for child_service in self._child_services],
            self._cleanup()
        )
        self.cleaned_up.set()

    async def cancel(self) -> None:
        """Trigger the CancelToken and wait for the cleaned_up event to be set."""
        if self.cancel_token.triggered:
            self.logger.warning("Tried to cancel %s, but it was already cancelled", self)
            return
        elif not self.is_running:
            raise RuntimeError("Cannot cancel a service that has not been started")

        self.logger.debug("Cancelling %s", self)
        self.cancel_token.trigger()
        try:
            await asyncio.wait_for(
                self.cleaned_up.wait(), timeout=self._wait_until_finished_timeout)
        except asyncio.futures.TimeoutError:
            self.logger.info("Timed out waiting for %s to finish its cleanup, exiting anyway", self)
        else:
            self.logger.debug("%s finished cleanly", self)

    @property
    def is_running(self) -> bool:
        return self._run_lock.locked()

    @abstractmethod
    async def _run(self) -> None:
        """Run the service's loop.

        Should return or raise OperationCancelled when the CancelToken is triggered.
        """
        raise NotImplementedError()

    @abstractmethod
    async def _cleanup(self) -> None:
        """Clean up any resources held by this service.

        Called after the service's _run() method returns.
        """
        raise NotImplementedError()


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
