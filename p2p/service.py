from abc import ABC, abstractmethod
import asyncio
from collections import UserList
import logging
from typing import Callable, List, Optional

from p2p.cancel_token import CancelToken
from p2p.exceptions import OperationCancelled


class BaseService(ABC):
    logger: logging.Logger = None
    # Number of seconds cancel() will wait for run() to finish.
    _wait_until_finished_timeout = 5

    def __init__(self, token: CancelToken=None) -> None:
        if self.logger is None:
            self.logger = logging.getLogger(self.__module__ + '.' + self.__class__.__name__)

        self._run_lock = asyncio.Lock()
        self.finished = asyncio.Event()
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

        Once _run() returns, set the finished event, call cleanup() and
        finished_callback (if one was passed).
        """
        if self.is_running:
            raise RuntimeError("Cannot start the service while it's already running")
        elif self.is_finished:
            raise RuntimeError("Cannot restart a service after it has completed")

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
            # Set self.finished before anything else so that other coroutines started by this
            # service exit while we wait for cleanup().
            self.finished.set()

            try:
                await self.cleanup()
            except Exception:
                self.logger.exception("Unexepected error during cleanup in %s", self)
                raise

            if finished_callback is not None:
                finished_callback(self)

    async def cleanup(self) -> None:
        """Run the service's _cleanup() coroutine."""
        await self._cleanup()

        self.cleaned_up.set()

    async def cancel(self):
        """Trigger the CancelToken and wait for the run() coroutine to finish."""
        if self.is_finished:
            self.logger.warning("Tried to cancel %s, but it was already finished", self)
        elif not self.is_running:
            raise RuntimeError("Cannot cancel a service that has not been started")

        self.logger.debug("Cancelling %s", self)
        self.cancel_token.trigger()
        try:
            await asyncio.wait_for(self.finished.wait(), timeout=self._wait_until_finished_timeout)
        except asyncio.futures.TimeoutError:
            self.logger.info("Timed out waiting for %s to finish, exiting anyway", self)

    @property
    def is_finished(self) -> bool:
        return self.finished.is_set()

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
