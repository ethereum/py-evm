import asyncio
import signal

from lahja import (
    Endpoint,
)

from p2p.service import (
    BaseService,
)


async def exit_on_signal(service_to_exit: BaseService, endpoint: Endpoint = None) -> None:
    loop = service_to_exit.get_event_loop()
    sigint_received = asyncio.Event()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        # TODO also support Windows
        loop.add_signal_handler(sig, sigint_received.set)

    await sigint_received.wait()
    try:
        await service_to_exit.cancel()
        if endpoint is not None:
            endpoint.stop()
        service_to_exit._executor.shutdown(wait=True)
    finally:
        loop.stop()
