import asyncio
from async_generator import (
    asynccontextmanager,
)
import signal
from typing import (
    AsyncGenerator,
)

from lahja import (
    Endpoint,
)

from p2p.service import (
    BaseService,
)


async def exit_with_service_and_endpoint(service_to_exit: BaseService, endpoint: Endpoint) -> None:
    async with exit_signal_with_service(service_to_exit):
        endpoint.stop()


async def exit_with_service(service_to_exit: BaseService) -> None:
    async with exit_signal_with_service(service_to_exit):
        pass


@asynccontextmanager
async def exit_signal_with_service(service_to_exit: BaseService) -> AsyncGenerator[None, None]:
    loop = service_to_exit.get_event_loop()
    async with exit_signal(loop):
        await service_to_exit.cancel()
        yield
        service_to_exit._executor.shutdown(wait=True)


@asynccontextmanager
async def exit_signal(loop: asyncio.AbstractEventLoop) -> AsyncGenerator[None, None]:
    sigint_received = asyncio.Event()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        # TODO also support Windows
        loop.add_signal_handler(sig, sigint_received.set)

    await sigint_received.wait()
    try:
        yield
    finally:
        loop.stop()
