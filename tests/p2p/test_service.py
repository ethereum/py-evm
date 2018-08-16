import asyncio

import pytest

from p2p.service import BaseService


class ParentService(BaseService):
    """A Service which just runs WaitService with run_daemon() and waits for its cancel token to
    be triggered.
    """

    async def _run(self):
        self.daemon = WaitService(token=self.cancel_token)
        self.run_daemon(self.daemon)
        await self.cancel_token.wait()


class WaitService(BaseService):

    async def _run(self):
        await self.cancel_token.wait()


@pytest.mark.asyncio
async def test_daemon_exit_causes_parent_cancellation():
    service = ParentService()
    asyncio.ensure_future(service.run())
    await asyncio.sleep(0.01)
    assert service.daemon.is_running
    await service.daemon.cancel()
    await asyncio.sleep(0.01)
    assert not service.is_running
    await service.events.cleaned_up.wait()
