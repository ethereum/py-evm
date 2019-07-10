import pytest

import trio

from p2p.trio_service import (
    ServiceManager,
    as_service,
)


async def do_service_lifecycle_check(manager,
                                     manager_run_fn,
                                     trigger_exit_condition_fn):
    async with trio.open_nursery() as nursery:
        assert manager.has_started is False
        assert manager.is_running is False
        assert manager.is_cancelled is False
        assert manager.is_stopped is False

        nursery.start_soon(manager_run_fn)

        with trio.fail_after(0.1):
            await manager.wait_started()

        assert manager.has_started is True
        assert manager.is_running is True
        assert manager.is_cancelled is False
        assert manager.is_stopped is False

        # trigger the service to exit
        trigger_exit_condition_fn()

        with trio.fail_after(10):
            await manager.wait_cancelled()

        assert manager.has_started is True
        assert manager.is_running is True
        assert manager.is_cancelled is True
        assert manager.is_stopped is False

        with trio.fail_after(0.1):
            await manager.wait_stopped()

        assert manager.has_started is True
        assert manager.is_running is False
        assert manager.is_cancelled is True
        assert manager.is_stopped is True


@pytest.mark.trio
async def test_trio_service_lifecycle_run_and_clean_exit():
    trigger_exit = trio.Event()

    @as_service
    async def ServiceTest(manager):
        await trigger_exit.wait()

    service = ServiceTest()
    manager = ServiceManager(service)

    await do_service_lifecycle_check(manager, manager.run, trigger_exit.set)


@pytest.mark.trio
async def test_trio_service_lifecycle_run_and_internal_cancellation():
    trigger_cancel = trio.Event()

    @as_service
    async def ServiceTest(manager):
        await trigger_cancel.wait()
        manager.cancel()

    service = ServiceTest()
    manager = ServiceManager(service)

    await do_service_lifecycle_check(manager, manager.run, trigger_cancel.set)


@pytest.mark.trio
async def test_trio_service_lifecycle_run_and_external_cancellation():

    @as_service
    async def ServiceTest(manager):
        while True:
            await trio.sleep(1)

    service = ServiceTest()
    manager = ServiceManager(service)

    await do_service_lifecycle_check(manager, manager.run, manager.cancel)


@pytest.mark.trio
async def test_trio_service_lifecycle_run_and_exception():
    trigger_error = trio.Event()

    @as_service
    async def ServiceTest(manager):
        await trigger_error.wait()
        raise RuntimeError("Service throwing error")

    service = ServiceTest()
    manager = ServiceManager(service)

    async def do_service_run():
        with pytest.raises(RuntimeError, match="Service throwing error"):
            await manager.run()

    await do_service_lifecycle_check(manager, do_service_run, trigger_error.set)
