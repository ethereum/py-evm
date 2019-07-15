import pytest

import trio

from p2p.trio_service import (
    Service,
    Manager,
    as_service,
    background_service,
)


class WaitCancelledService(Service):
    async def run(self) -> None:
        await self.manager.wait_cancelled()


async def do_service_lifecycle_check(manager,
                                     manager_run_fn,
                                     trigger_exit_condition_fn,
                                     should_be_cancelled):
    async with trio.open_nursery() as nursery:
        assert manager.is_started is False
        assert manager.is_running is False
        assert manager.is_cancelled is False
        assert manager.is_stopped is False

        nursery.start_soon(manager_run_fn)

        with trio.fail_after(0.1):
            await manager.wait_started()

        assert manager.is_started is True
        assert manager.is_running is True
        assert manager.is_cancelled is False
        assert manager.is_stopped is False

        # trigger the service to exit
        trigger_exit_condition_fn()

        if should_be_cancelled:
            with trio.fail_after(0.01):
                await manager.wait_cancelled()

            assert manager.is_started is True
            # non-deterministic for whether the service would register as
            # *running* or *stopped* at this stage because it may have stopped
            # or it may be stopping.
            assert manager.is_cancelled is True

        with trio.fail_after(0.1):
            await manager.wait_stopped()

        assert manager.is_started is True
        assert manager.is_running is False
        assert manager.is_cancelled is should_be_cancelled
        assert manager.is_stopped is True


def test_service_manager_initial_state():
    service = WaitCancelledService()
    manager = Manager(service)

    assert manager.is_started is False
    assert manager.is_running is False
    assert manager.is_cancelled is False
    assert manager.is_stopped is False


@pytest.mark.trio
async def test_trio_service_lifecycle_run_and_clean_exit():
    trigger_exit = trio.Event()

    @as_service
    async def ServiceTest(manager):
        await trigger_exit.wait()

    service = ServiceTest()
    manager = Manager(service)

    await do_service_lifecycle_check(
        manager=manager,
        manager_run_fn=manager.run,
        trigger_exit_condition_fn=trigger_exit.set,
        should_be_cancelled=False,
    )


@pytest.mark.trio
async def test_trio_service_lifecycle_run_and_external_cancellation():

    @as_service
    async def ServiceTest(manager):
        while True:
            await trio.sleep(0.1)

    service = ServiceTest()
    manager = Manager(service)

    await do_service_lifecycle_check(
        manager=manager,
        manager_run_fn=manager.run,
        trigger_exit_condition_fn=manager.cancel,
        should_be_cancelled=True,
    )


@pytest.mark.trio
async def test_trio_service_lifecycle_run_and_exception():
    trigger_error = trio.Event()

    @as_service
    async def ServiceTest(manager):
        await trigger_error.wait()
        raise RuntimeError("Service throwing error")

    service = ServiceTest()
    manager = Manager(service)

    async def do_service_run():
        with pytest.raises(RuntimeError, match="Service throwing error"):
            await manager.run()

    await do_service_lifecycle_check(
        manager=manager,
        manager_run_fn=do_service_run,
        trigger_exit_condition_fn=trigger_error.set,
        should_be_cancelled=True,
    )


@pytest.mark.trio
async def test_trio_service_background_service_context_manager():
    service = WaitCancelledService()

    async with background_service(service) as manager:
        # ensure the manager property is set.
        assert hasattr(service, 'manager')
        assert service.manager is manager

        assert manager.is_started is True
        assert manager.is_running is True
        assert manager.is_cancelled is False
        assert manager.is_stopped is False

    assert manager.is_started is True
    assert manager.is_running is False
    assert manager.is_cancelled is True
    assert manager.is_stopped is True


@pytest.mark.trio
async def test_trio_service_manager_stop():
    service = WaitCancelledService()

    async with background_service(service) as manager:
        assert manager.is_started is True
        assert manager.is_running is True
        assert manager.is_cancelled is False
        assert manager.is_stopped is False

        await manager.stop()

        assert manager.is_started is True
        assert manager.is_running is False
        assert manager.is_cancelled is True
        assert manager.is_stopped is True


@pytest.mark.trio
async def test_trio_service_manager_run_task():
    task_event = trio.Event()

    @as_service
    async def RunTaskService(manager):
        async def task_fn():
            task_event.set()
        manager.run_task(task_fn)
        await manager.wait_cancelled()

    async with background_service(RunTaskService()):
        with trio.fail_after(0.1):
            await task_event.wait()


@pytest.mark.trio
async def test_trio_service_manager_run_task_waits_for_task_completion():
    task_event = trio.Event()

    @as_service
    async def RunTaskService(manager):
        async def task_fn():
            await trio.sleep(0.01)
            task_event.set()
        manager.run_task(task_fn)
        # the task is set to run in the background but then  the service exits.
        # We want to be sure that the task is allowed to continue till
        # completion unless explicitely cancelled.

    async with background_service(RunTaskService()):
        with trio.fail_after(0.1):
            await task_event.wait()


@pytest.mark.trio
async def test_trio_service_manager_run_task_can_still_cancel_after_run_finishes():
    task_event = trio.Event()
    service_finished = trio.Event()

    @as_service
    async def RunTaskService(manager):
        async def task_fn():
            # this will never complete
            await task_event.wait()

        manager.run_task(task_fn)
        # the task is set to run in the background but then  the service exits.
        # We want to be sure that the task is allowed to continue till
        # completion unless explicitely cancelled.
        service_finished.set()

    async with background_service(RunTaskService()) as manager:
        with trio.fail_after(0.01):
            await service_finished.wait()

        # show that the service hangs waiting for the task to complete.
        with trio.move_on_after(0.01) as cancel_scope:
            await manager.wait_stopped()
        assert cancel_scope.cancelled_caught is True

        # trigger cancellation and see that the service actually stops
        manager.cancel()
        with trio.fail_after(0.01):
            await manager.wait_stopped()


@pytest.mark.trio
async def test_trio_service_manager_propogates_and_records_exceptions():
    @as_service
    async def ThrowErrorService(manager):
        raise RuntimeError('this is the error')

    service = ThrowErrorService()
    manager = Manager(service)

    assert manager.did_error is False

    with pytest.raises(RuntimeError, match='this is the error'):
        await manager.run()

    assert manager.did_error is True
