import asyncio

from cancel_token import OperationCancelled
import pytest

from p2p.service import BaseService, run_service


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

    assert service.daemon.is_operational
    assert service.daemon.is_running

    await service.daemon.cancel()
    await asyncio.sleep(0.01)

    assert not service.is_operational
    assert not service.is_running

    await asyncio.wait_for(service.events.cleaned_up.wait(), timeout=1)


@pytest.mark.asyncio
async def test_cancel_exits_async_generator():
    service = WaitService()
    asyncio.ensure_future(service.run())

    async def cancel_soon():
        await service.sleep(0.05)
        await service.cancel()

    asyncio.ensure_future(cancel_soon())

    async def async_iterator():
        yield 1
        await asyncio.sleep(0.05)
        assert False, "iterator should have been cancelled by now"

    try:
        async for val in service.wait_iter(async_iterator()):
            assert val == 1
    except OperationCancelled:
        pass
    else:
        assert False, "iterator should have been cancelled during iteration"

    await service.cancel()


@pytest.mark.asyncio
async def test_service_tasks_do_not_leak_memory():
    service = WaitService()
    asyncio.ensure_future(service.run())

    end = asyncio.Event()

    async def run_until_end():
        await end.wait()

    service.run_task(run_until_end())

    # inspect internals to determine if memory is leaking

    # confirm that task is tracked:
    assert len(service._tasks) == 1

    end.set()
    # allow the coro to exit
    await asyncio.sleep(0)

    # confirm that task is no longer tracked:
    assert len(service._tasks) == 0

    # test cleanup
    await service.cancel()


@pytest.mark.asyncio
async def test_service_children_do_not_leak_memory():
    parent = WaitService()
    child = WaitService()
    asyncio.ensure_future(parent.run())

    parent.run_child_service(child)

    # inspect internals to determine if memory is leaking

    # confirm that child service is tracked:
    assert len(parent._child_services) == 1

    # give child a chance to start
    await asyncio.sleep(0)

    # ... and then end it
    await child.cancel()

    # remove the final reference to the child service
    del child

    # confirm that child service is no longer tracked:
    assert len(parent._child_services) == 0

    # test cleanup
    await parent.cancel()


@pytest.mark.asyncio
async def test_run_service_context_manager_lifecycle():
    service = WaitService()

    assert not service.is_operational
    assert not service.is_cancelled
    assert not service.is_running

    async with run_service(service) as running_service:
        assert running_service is service

        assert service.is_operational
        assert not service.is_cancelled
        assert service.is_running

    assert not service.is_operational
    assert service.is_cancelled
    assert not service.is_running


class BlowUp(Exception):
    pass


@pytest.mark.asyncio
async def test_run_service_context_manager_lifecycle_with_exception():
    service = WaitService()

    assert not service.is_operational
    assert not service.is_cancelled
    assert not service.is_running

    with pytest.raises(BlowUp):
        async with run_service(service) as running_service:
            assert running_service is service

            assert service.is_operational
            assert not service.is_cancelled
            assert service.is_running

            raise BlowUp

    assert not service.is_operational
    assert service.is_cancelled
    assert not service.is_running
