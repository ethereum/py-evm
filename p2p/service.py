from abc import ABC, abstractmethod
import asyncio
from collections import UserList
import logging
from typing import Any, Awaitable, Callable, List, Optional

from p2p.cancel_token import CancelToken, wait_with_token
from p2p.exceptions import OperationCancelled


class BaseService(ABC):
    logger: logging.Logger = None
    # Number of seconds cancel() will wait for run() to finish.
    _wait_until_finished_timeout = 5

    def __init__(self, token: CancelToken=None) -> None:
        if self.logger is None:
            self.logger = logging.getLogger(self.__module__ + '.' + self.__class__.__name__)

        self._run_lock = asyncio.Lock()
        self.cleaned_up = asyncio.Event()

        base_token = CancelToken(type(self).__name__)
        if token is None:
            self.cancel_token = base_token
        else:
            self.cancel_token = base_token.chain(token)

    async def wait(
            self, awaitable: Awaitable, token: CancelToken = None, timeout: float = None) -> Any:
        """See wait_first()"""
        return await self.wait_first(awaitable, token=token, timeout=timeout)

    async def wait_first(
            self, *awaitables: Awaitable, token: CancelToken = None, timeout: float = None) -> Any:
        """Wait for the first awaitable to complete, unless we timeout or the token chain is triggered.

        The given token is chained with this service's token, so triggering either will cancel
        this.

        Returns the result of the first one to complete.

        Raises TimeoutError if we timeout or OperationCancelled if the token chain is triggered.

        All pending futures are cancelled before returning.
        """
        if token is None:
            token_chain = self.cancel_token
        else:
            token_chain = token.chain(self.cancel_token)
        return await wait_with_token(*awaitables, token=token_chain, timeout=timeout)

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
            self.logger.exception("Unexpected error in %s, exiting", self)
        else:
            self.logger.debug("%s finished cleanly", self)
        finally:
            # Trigger our cancel token to ensure all pending asyncio tasks and background
            # coroutines started by this service exit cleanly.
            self.cancel_token.trigger()

            await self.cleanup()

            if finished_callback is not None:
                finished_callback(self)

    async def cleanup(self) -> None:
        """Run the service's _cleanup() coroutine and sets the cleaned_up event."""
        await self._cleanup()
        self.cleaned_up.set()

    async def cancel(self):
        """Trigger the CancelToken and wait for the cleaned_up event to be set."""
        if not self.is_running:
            raise RuntimeError("Cannot cancel a service that has not been started")
        elif self.cancel_token.triggered:
            self.logger.warning("Tried to cancel %s, but it was already cancelled", self)

        self.logger.debug("Cancelling %s", self)
        self.cancel_token.trigger()
        try:
            await asyncio.wait_for(
                self.cleaned_up.wait(), timeout=self._wait_until_finished_timeout)
        except asyncio.futures.TimeoutError:
            self.logger.info("Timed out waiting for %s to finish its cleanup, exiting anyway", self)

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


class EmptyService(BaseService):
    async def _run(self) -> None:
        pass

    async def _cleanup(self) -> None:
        pass


class ServiceContext(UserList):
    """
    Run a sequence of services in a context manager, closing them all cleanly on exit.
    """
    logger = logging.getLogger("p2p.service.ServiceContext")

    def __init__(self, services: List[BaseService] = None) -> None:
        if services is None:
            super().__init__()
        else:
            super().__init__(services)
        self.started_services: List[BaseService] = []
        self._run_lock = asyncio.Lock()

    async def __aenter__(self):
        if self._run_lock.locked():
            raise RuntimeError("Cannot enter ServiceContext while it is already running")
        await self._run_lock.acquire()

        self.started_services = list(self.data)
        for service in self.started_services:
            asyncio.ensure_future(service.run())

    async def __aexit__(self, exc_type, exc, tb):
        service_cancellations = [service.cancel() for service in self.started_services]
        results = await asyncio.gather(*service_cancellations, return_exceptions=True)
        for service, result in zip(self.started_services, results):
            if isinstance(result, BaseException):
                self.logger.warning(
                    "Exception while cancelling service %r: %r",
                    service,
                    result,
                )
        self.started_services = []
        self._run_lock.release()
