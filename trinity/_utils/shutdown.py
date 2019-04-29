import asyncio
from async_generator import (
    asynccontextmanager,
)
import signal
from typing import (
    AsyncGenerator,
)

from p2p.service import (
    BaseService,
)

from trinity.endpoint import (
    TrinityEventBusEndpoint,
)


async def exit_with_endpoint_and_services(endpoint: TrinityEventBusEndpoint,
                                          *services_to_exit: BaseService) -> None:
    async with exit_signal_with_services(*services_to_exit):
        endpoint.stop()


async def exit_with_services(*services_to_exit: BaseService) -> None:
    async with exit_signal_with_services(*services_to_exit):
        pass


@asynccontextmanager
async def exit_signal_with_services(*services_to_exit: BaseService,
                                    ) -> AsyncGenerator[None, None]:
    loop_ids = set(service.get_event_loop() for service in services_to_exit)
    if len(loop_ids) != 1:
        raise ValueError(f"Multiple event loops found: {loop_ids}")
    loop = services_to_exit[0].get_event_loop()
    async with exit_signal(loop):
        await asyncio.gather(*(service.cancel() for service in services_to_exit))
        yield


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
