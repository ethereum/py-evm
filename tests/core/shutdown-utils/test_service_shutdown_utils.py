import asyncio
import multiprocessing
import os
import signal

import pytest

from p2p.service import BaseService

from trinity._utils.shutdown import (
    exit_with_services,
)


class SimpleService(BaseService):
    def __init__(self, ready_to_kill_event, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ready_to_kill_event = ready_to_kill_event

    async def _run(self):
        self.ready_to_kill_event.set()
        await self.cancellation()


def run_service(ready_to_kill_event):
    loop = asyncio.get_event_loop()

    service = SimpleService(ready_to_kill_event, loop=loop)

    asyncio.ensure_future(service.run())
    asyncio.ensure_future(exit_with_services(service))

    loop.run_forever()
    loop.close()

    assert service.is_cancelled


@pytest.mark.parametrize('sig', (signal.SIGINT, signal.SIGTERM))
@pytest.mark.asyncio
async def test_exit_with_endpoind_and_services_facilitates_clean_shutdown(sig):
    ready_to_kill_event = multiprocessing.Event()
    proc = multiprocessing.Process(target=run_service, args=(ready_to_kill_event,))
    proc.start()

    ready_to_kill_event.wait()
    os.kill(proc.pid, sig)
    proc.join(timeout=1)
