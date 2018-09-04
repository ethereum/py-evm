import asyncio
from enum import Enum, auto

from eth_utils import (
    ValidationError,
)
from eth_utils.toolz import identity
import pytest

from trinity.utils.datastructures import (
    BaseTaskCompletion,
    TaskIntegrator,
)

DEFAULT_TIMEOUT = 0.05


async def wait(coro, timeout=DEFAULT_TIMEOUT):
    return await asyncio.wait_for(coro, timeout=timeout)


class OneTask(Enum):
    one = auto()


class TwoTasks(Enum):
    Task1 = auto()
    Task2 = auto()


IdentityOneCompletion = BaseTaskCompletion.factory(OneTask, identity, lambda x: x - 1)
IdentityTwoCompletion = BaseTaskCompletion.factory(TwoTasks, identity, lambda x: x - 1)


@pytest.mark.asyncio
async def test_simplest_path():
    ti = TaskIntegrator(IdentityTwoCompletion)
    ti.set_last_completion(3)
    ti.prepare((4, ))
    ti.finish(TwoTasks.Task1, (4, ))
    ti.finish(TwoTasks.Task2, (4, ))
    completed = await wait(ti.next_completed())
    assert completed == (4, )


@pytest.mark.asyncio
async def test_cannot_finish_before_prepare():
    ti = TaskIntegrator(IdentityTwoCompletion)
    ti.set_last_completion(3)
    with pytest.raises(ValidationError):
        ti.finish(TwoTasks.Task1, (4, ))


@pytest.mark.asyncio
async def test_two_steps_simultaneous_complete():
    ti = TaskIntegrator(IdentityOneCompletion)
    ti.set_last_completion(3)
    ti.prepare((4, 5))
    ti.finish(OneTask.one, (4, ))
    ti.finish(OneTask.one, (5, ))

    completed = await wait(ti.next_completed())
    assert completed == (4, 5)


@pytest.mark.asyncio
async def test_pruning():
    # make a number depend on the mod10, so 4 and 14 both depend on task 3
    Mod10Dependency = BaseTaskCompletion.factory(OneTask, identity, lambda x: (x % 10) - 1)
    ti = TaskIntegrator(Mod10Dependency, max_depth=2)
    ti.set_last_completion(3)
    ti.prepare((4, 5, 6))
    ti.finish(OneTask.one, (4, 5, 6))

    # it's fine to prepare a task that depends up to two back in history
    # this depends on 5
    ti.prepare((16, ))
    # this depends on 4
    ti.prepare((15, ))

    # but depending 3 back in history should raise a validation error, because it's pruned
    with pytest.raises(ValidationError):
        # this depends on 3
        ti.prepare((14, ))

    # test the same concept, but after pruning more than just the starting task...
    ti.prepare((7, ))
    ti.finish(OneTask.one, (7, ))

    ti.prepare((16, ))
    ti.prepare((17, ))
    with pytest.raises(ValidationError):
        ti.prepare((15, ))


@pytest.mark.asyncio
async def test_wait_forever():
    ti = TaskIntegrator(IdentityOneCompletion)
    try:
        finished = await wait(ti.next_completed())
    except asyncio.TimeoutError:
        pass
    else:
        assert False, f"No steps should complete, but got {finished!r}"


def test_finish_same_task_twice():
    ti = TaskIntegrator(IdentityTwoCompletion)
    ti.set_last_completion(1)
    ti.prepare((2, ))
    ti.finish(TwoTasks.Task1, (2,))
    with pytest.raises(ValidationError):
        ti.finish(TwoTasks.Task1, (2,))


@pytest.mark.asyncio
async def test_finish_different_entry_at_same_step():

    def previous_even_number(num):
        return ((num - 1) // 2) * 2

    DependsOnEvens = BaseTaskCompletion.factory(OneTask, identity, previous_even_number)
    ti = TaskIntegrator(DependsOnEvens)

    ti.set_last_completion(2)

    ti.prepare((3, 4))

    # depends on 2
    ti.finish(OneTask.one, (3,))

    # also depends on 2
    ti.finish(OneTask.one, (4,))

    completed = await wait(ti.next_completed())
    assert completed == (3, 4)


@pytest.mark.asyncio
async def test_return_original_entry():
    # for no particular reason, the id is 3 before the number
    DependsOnEvens = BaseTaskCompletion.factory(OneTask, lambda x: x - 3, lambda x: x - 4)
    ti = TaskIntegrator(DependsOnEvens)

    # translates to id -1
    ti.set_last_completion(2)

    ti.prepare((3, 4))

    # translates to id 0
    ti.finish(OneTask.one, (3,))

    # translates to id 1
    ti.finish(OneTask.one, (4,))

    entries = await wait(ti.next_completed())

    # make sure that the original task is returned, not the id
    assert entries == (3, 4)


def test_finish_with_unrecognized_task():
    ti = TaskIntegrator(IdentityTwoCompletion)
    ti.set_last_completion(1)
    with pytest.raises(ValidationError):
        ti.finish('UNRECOGNIZED_TASK', (2,))


def test_finish_before_setting_start_val():
    ti = TaskIntegrator(IdentityTwoCompletion)
    with pytest.raises(ValidationError):
        ti.finish(TwoTasks.Task1, (2,))


def test_finish_too_early():
    ti = TaskIntegrator(IdentityTwoCompletion)
    ti.set_last_completion(3)
    with pytest.raises(ValidationError):
        ti.finish(TwoTasks.Task1, (3,))


def test_empty_completion():
    ti = TaskIntegrator(IdentityTwoCompletion)
    with pytest.raises(ValidationError):
        ti.finish(TwoTasks.Task1, tuple())


def test_empty_enum():

    class NoTasks(Enum):
        pass

    with pytest.raises(ValidationError):
        BaseTaskCompletion.factory(NoTasks, identity, lambda x: x - 1)
