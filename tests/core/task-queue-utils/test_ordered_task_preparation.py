import asyncio
from enum import Enum, auto
import time
from typing import NamedTuple

from eth_utils import (
    ValidationError,
)
from eth_utils.toolz import identity
import pytest

from trinity._utils.datastructures import (
    DuplicateTasks,
    MissingDependency,
    OrderedTaskPreparation,
)

DEFAULT_TIMEOUT = 0.05


async def wait(coro, timeout=DEFAULT_TIMEOUT):
    return await asyncio.wait_for(coro, timeout=timeout)


class NoPrerequisites(Enum):
    pass


class OnePrereq(Enum):
    one = auto()


class TwoPrereqs(Enum):
    Prereq1 = auto()
    Prereq2 = auto()


@pytest.mark.asyncio
async def test_simplest_path():
    ti = OrderedTaskPreparation(TwoPrereqs, identity, lambda x: x - 1)
    ti.set_finished_dependency(3)
    ti.register_tasks((4, ))
    ti.finish_prereq(TwoPrereqs.Prereq1, (4, ))
    ti.finish_prereq(TwoPrereqs.Prereq2, (4, ))
    ready = await wait(ti.ready_tasks())
    assert ready == (4, )


@pytest.mark.asyncio
async def test_cannot_finish_before_prepare():
    ti = OrderedTaskPreparation(TwoPrereqs, identity, lambda x: x - 1)
    ti.set_finished_dependency(3)
    with pytest.raises(ValidationError):
        ti.finish_prereq(TwoPrereqs.Prereq1, (4, ))


@pytest.mark.asyncio
async def test_two_steps_simultaneous_complete():
    ti = OrderedTaskPreparation(OnePrereq, identity, lambda x: x - 1)
    ti.set_finished_dependency(3)
    ti.register_tasks((4, 5))
    ti.finish_prereq(OnePrereq.one, (4, ))
    ti.finish_prereq(OnePrereq.one, (5, ))

    completed = await wait(ti.ready_tasks())
    assert completed == (4, 5)


@pytest.mark.asyncio
async def test_pruning():
    # make a number task depend on the mod10, so 4 and 14 both depend on task 3
    ti = OrderedTaskPreparation(OnePrereq, identity, lambda x: (x % 10) - 1, max_depth=2)
    ti.set_finished_dependency(3)
    ti.register_tasks((4, 5, 6))
    ti.finish_prereq(OnePrereq.one, (4, 5, 6))

    # it's fine to prepare a task that depends up to two back in history
    # this depends on 5
    ti.register_tasks((16, ))
    # this depends on 4
    ti.register_tasks((15, ))

    # but depending 3 back in history should raise a validation error, because it's pruned
    with pytest.raises(MissingDependency):
        # this depends on 3
        ti.register_tasks((14, ))

    # test the same concept, but after pruning more than just the starting task...
    ti.register_tasks((7, ))
    ti.finish_prereq(OnePrereq.one, (7, ))

    ti.register_tasks((26, ))
    ti.register_tasks((27, ))
    with pytest.raises(MissingDependency):
        ti.register_tasks((25, ))


@pytest.mark.asyncio
async def test_wait_forever():
    ti = OrderedTaskPreparation(OnePrereq, identity, lambda x: x - 1)
    try:
        finished = await wait(ti.ready_tasks())
    except asyncio.TimeoutError:
        pass
    else:
        assert False, f"No steps should complete, but got {finished!r}"


def test_finish_same_task_twice():
    ti = OrderedTaskPreparation(TwoPrereqs, identity, lambda x: x - 1)
    ti.set_finished_dependency(1)
    ti.register_tasks((2, ))
    ti.finish_prereq(TwoPrereqs.Prereq1, (2,))
    with pytest.raises(ValidationError):
        ti.finish_prereq(TwoPrereqs.Prereq1, (2,))


@pytest.mark.asyncio
async def test_finish_different_entry_at_same_step():

    def previous_even_number(num):
        return ((num - 1) // 2) * 2

    ti = OrderedTaskPreparation(OnePrereq, identity, previous_even_number)

    ti.set_finished_dependency(2)

    ti.register_tasks((3, 4))

    # depends on 2
    ti.finish_prereq(OnePrereq.one, (3,))

    # also depends on 2
    ti.finish_prereq(OnePrereq.one, (4,))

    completed = await wait(ti.ready_tasks())
    assert completed == (3, 4)


@pytest.mark.asyncio
async def test_return_original_entry():
    # for no particular reason, the id is 3 before the number
    ti = OrderedTaskPreparation(OnePrereq, lambda x: x - 3, lambda x: x - 4)

    # translates to id -1
    ti.set_finished_dependency(2)

    ti.register_tasks((3, 4))

    # translates to id 0
    ti.finish_prereq(OnePrereq.one, (3,))

    # translates to id 1
    ti.finish_prereq(OnePrereq.one, (4,))

    entries = await wait(ti.ready_tasks())

    # make sure that the original task is returned, not the id
    assert entries == (3, 4)


def test_finish_with_unrecognized_task():
    ti = OrderedTaskPreparation(TwoPrereqs, identity, lambda x: x - 1)
    ti.set_finished_dependency(1)
    with pytest.raises(ValidationError):
        ti.finish_prereq('UNRECOGNIZED_TASK', (2,))


def test_finish_before_setting_start_val():
    ti = OrderedTaskPreparation(TwoPrereqs, identity, lambda x: x - 1)
    with pytest.raises(ValidationError):
        ti.finish_prereq(TwoPrereqs.Prereq1, (2,))


def test_finish_too_early():
    ti = OrderedTaskPreparation(TwoPrereqs, identity, lambda x: x - 1)
    ti.set_finished_dependency(3)
    with pytest.raises(ValidationError):
        ti.finish_prereq(TwoPrereqs.Prereq1, (3,))


def test_empty_completion():
    ti = OrderedTaskPreparation(TwoPrereqs, identity, lambda x: x - 1)
    with pytest.raises(ValidationError):
        ti.finish_prereq(TwoPrereqs.Prereq1, tuple())


def test_reregister_duplicates():
    ti = OrderedTaskPreparation(TwoPrereqs, identity, lambda x: x - 1)
    ti.set_finished_dependency(1)
    ti.register_tasks((2, ))
    with pytest.raises(DuplicateTasks):
        ti.register_tasks((2, ))


@pytest.mark.asyncio
async def test_no_prereq_tasks():
    ti = OrderedTaskPreparation(NoPrerequisites, identity, lambda x: x - 1)
    ti.set_finished_dependency(1)
    ti.register_tasks((2, 3))

    # with no prerequisites, tasks are *immediately* finished, as long as they are in order
    finished = await wait(ti.ready_tasks())
    assert finished == (2, 3)


@pytest.mark.asyncio
async def test_ignore_duplicates():
    ti = OrderedTaskPreparation(NoPrerequisites, identity, lambda x: x - 1)
    ti.set_finished_dependency(1)
    ti.register_tasks((2, ))
    # this will ignore the 2 task:
    ti.register_tasks((2, 3), ignore_duplicates=True)
    # this will be completely ignored:
    ti.register_tasks((2, 3), ignore_duplicates=True)

    # with no prerequisites, tasks are *immediately* finished, as long as they are in order
    finished = await wait(ti.ready_tasks())
    assert finished == (2, 3)


@pytest.mark.asyncio
async def test_register_out_of_order():
    ti = OrderedTaskPreparation(OnePrereq, identity, lambda x: x - 1, accept_dangling_tasks=True)
    ti.set_finished_dependency(1)
    ti.register_tasks((4, 5))
    ti.finish_prereq(OnePrereq.one, (4, 5))

    try:
        finished = await wait(ti.ready_tasks())
    except asyncio.TimeoutError:
        pass
    else:
        assert False, f"No steps should be ready, but got {finished!r}"

    ti.register_tasks((2, 3))
    ti.finish_prereq(OnePrereq.one, (2, 3))
    finished = await wait(ti.ready_tasks())
    assert finished == (2, 3, 4, 5)


@pytest.mark.asyncio
async def test_no_prereq_tasks_out_of_order():
    ti = OrderedTaskPreparation(
        NoPrerequisites,
        identity,
        lambda x: x - 1,
        accept_dangling_tasks=True,
    )
    ti.set_finished_dependency(1)
    ti.register_tasks((4, 5))

    try:
        finished = await wait(ti.ready_tasks())
    except asyncio.TimeoutError:
        pass
    else:
        assert False, f"No steps should be ready, but got {finished!r}"

    ti.register_tasks((2, 3))

    # with no prerequisites, tasks are *immediately* finished, as long as they are in order
    finished = await wait(ti.ready_tasks())
    assert finished == (2, 3, 4, 5)


@pytest.mark.asyncio
async def test_finished_dependency_midstream():
    """
    We need to be able to mark dependencies as finished, after task completion
    """
    ti = OrderedTaskPreparation(TwoPrereqs, identity, lambda x: x - 1)
    ti.set_finished_dependency(3)
    ti.register_tasks((4, ))
    ti.finish_prereq(TwoPrereqs.Prereq1, (4, ))
    ti.finish_prereq(TwoPrereqs.Prereq2, (4, ))
    ready = await wait(ti.ready_tasks())
    assert ready == (4, )

    # now start in a discontinuous series of tasks
    with pytest.raises(MissingDependency):
        ti.register_tasks((6, ))

    ti.set_finished_dependency(5)
    ti.register_tasks((6, ))
    ti.finish_prereq(TwoPrereqs.Prereq1, (6, ))
    ti.finish_prereq(TwoPrereqs.Prereq2, (6, ))
    ready = await wait(ti.ready_tasks())
    assert ready == (6, )


def test_dangled_pruning():
    # make a number task depend on the mod10, so 4 and 14 both depend on task 3
    ti = OrderedTaskPreparation(
        NoPrerequisites,
        identity,
        lambda x: (x % 10) - 1,
        max_depth=2,
        accept_dangling_tasks=True,
    )
    ti.set_finished_dependency(3)
    ti.register_tasks((5, 6))

    # No obvious way to check which tasks are pruned when accepting dangling tasks,
    # so use an internal API until a better option is found:
    # Nothing should be pruned yet
    assert 3 in ti._tasks

    ti.register_tasks((4, ))

    # 3 should be pruned now
    assert 3 not in ti._tasks
    assert 4 in ti._tasks

    ti.register_tasks((7, ))

    # 4 should be pruned now
    assert 4 not in ti._tasks


class TaskID(NamedTuple):
    idx: int
    fork: int  # noqa: E701 -- flake8 3.5.0 seems confused by py3.6+ NamedTuple syntax


class Task(NamedTuple):
    idx: int
    fork: int  # noqa: E701 -- flake8 3.5.0 seems confused by py3.6+ NamedTuple syntax
    parent_fork: int


def task_id(task):
    return TaskID(task.idx, task.fork)


def fork_prereq(task):
    # allow tasks to fork for a few in a row
    return TaskID(task.idx - 1, task.parent_fork)


def test_forked_pruning():
    ti = OrderedTaskPreparation(
        NoPrerequisites,
        task_id,
        fork_prereq,
        max_depth=2,
    )
    ti.set_finished_dependency(Task(0, 0, 0))
    ti.register_tasks((
        Task(1, 0, 0),
        Task(2, 0, 0),
        Task(2, 1, 0),
    ))
    ti.register_tasks((
        Task(3, 0, 0),
        Task(3, 1, 1),
    ))
    ti.register_tasks((
        Task(4, 0, 0),
        Task(4, 1, 1),
    ))
    ti.register_tasks((
        Task(5, 0, 0),
        Task(6, 0, 0),
        Task(7, 0, 0),
        Task(8, 0, 0),
        Task(9, 0, 0),
        Task(10, 0, 0),
    ))
    ti.register_tasks((
        Task(5, 1, 1),
    ))

    assert TaskID(1, 0) not in ti._tasks
    assert TaskID(2, 0) not in ti._tasks
    assert TaskID(3, 0) not in ti._tasks
    assert TaskID(4, 0) not in ti._tasks
    assert TaskID(5, 0) not in ti._tasks
    assert TaskID(2, 1) not in ti._tasks
    assert TaskID(10, 0) in ti._tasks


def test_forked_pruning_dangling():
    ti = OrderedTaskPreparation(
        OnePrereq,
        task_id,
        fork_prereq,
        max_depth=2,
        accept_dangling_tasks=True,
    )
    ti.set_finished_dependency(Task(0, 0, 0))
    ti.register_tasks((
        Task(2, 0, 0),
        Task(2, 1, 0),
    ))
    ti.finish_prereq(OnePrereq.one, (
        Task(2, 0, 0),
        Task(2, 1, 0),
    ))

    ti.register_tasks((
        Task(3, 0, 0),
        Task(3, 1, 1),
    ))
    ti.finish_prereq(OnePrereq.one, (
        Task(3, 0, 0),
        Task(3, 1, 1),
    ))

    ti.register_tasks((
        Task(4, 0, 0),
        Task(4, 1, 1),
    ))
    ti.finish_prereq(OnePrereq.one, (
        Task(4, 0, 0),
        Task(4, 1, 1),
    ))

    ti.register_tasks((
        Task(5, 0, 0),
        Task(6, 0, 0),
        Task(7, 0, 0),
        Task(8, 0, 0),
        Task(9, 0, 0),
        Task(10, 0, 0),
    ))
    ti.finish_prereq(OnePrereq.one, (
        Task(5, 0, 0),
        Task(6, 0, 0),
        Task(7, 0, 0),
        Task(8, 0, 0),
        Task(9, 0, 0),
        Task(10, 0, 0),
    ))

    ti.register_tasks((
        Task(5, 1, 1),
    ))
    ti.finish_prereq(OnePrereq.one, (
        Task(5, 1, 1),
    ))

    ti.register_tasks((
        Task(1, 0, 0),
    ))
    ti.finish_prereq(OnePrereq.one, (
        Task(1, 0, 0),
    ))

    ti.register_tasks((
        Task(11, 0, 0),
        Task(12, 0, 0),
        Task(13, 0, 0),
        Task(14, 0, 0),
        Task(15, 0, 0),
        Task(16, 0, 0),
        Task(17, 0, 0),
        Task(18, 0, 0),
        Task(19, 0, 0),
        Task(20, 0, 0),
        Task(6, 1, 1),
        Task(7, 1, 1),
        Task(8, 1, 1),
        Task(9, 1, 1),
    ))
    ti.finish_prereq(OnePrereq.one, (
        Task(11, 0, 0),
        Task(12, 0, 0),
        Task(13, 0, 0),
        Task(14, 0, 0),
        Task(15, 0, 0),
        Task(16, 0, 0),
        Task(17, 0, 0),
        Task(18, 0, 0),
        Task(19, 0, 0),
        Task(20, 0, 0),
        Task(6, 1, 1),
        Task(7, 1, 1),
        Task(8, 1, 1),
        Task(9, 1, 1),
    ))

    assert TaskID(6, 1) not in ti._tasks
    assert TaskID(7, 1) in ti._tasks
    assert TaskID(17, 0) not in ti._tasks
    assert TaskID(18, 0) in ti._tasks


def test_re_fork_at_prune_boundary():
    def task_id(task):
        return TaskID(task.idx, task.fork)

    def fork_prereq(task):
        # allow tasks to fork for a few in a row
        return TaskID(task.idx - 1, task.parent_fork)

    ti = OrderedTaskPreparation(
        NoPrerequisites,
        task_id,
        fork_prereq,
        max_depth=2,
    )
    ti.set_finished_dependency(Task(0, 0, 0))
    ti.register_tasks((
        Task(1, 0, 0),
        Task(2, 0, 0),
        Task(2, 1, 0),
    ))
    ti.register_tasks((
        Task(3, 0, 0),
        Task(3, 1, 1),
    ))
    ti.register_tasks((
        Task(4, 0, 0),
        Task(4, 1, 1),
        Task(4, 2, 1),
    ))
    ti.register_tasks((
        Task(5, 0, 0),
        Task(6, 0, 0),
        Task(7, 0, 0),
        Task(8, 0, 0),
        Task(9, 0, 0),
        Task(10, 0, 0),
    ))
    ti.register_tasks((
        Task(5, 1, 1),
        Task(5, 2, 2),
        Task(5, 3, 2),
    ))
    ti.register_tasks((
        Task(6, 3, 3),
        Task(7, 3, 3),
        Task(8, 3, 3),
        Task(9, 3, 3),
    ))


def test_pruning_speed():
    length = 10000
    ti = OrderedTaskPreparation(
        NoPrerequisites,
        identity,
        lambda x: x - 1,
        max_depth=length,
    )
    ti.set_finished_dependency(-1)
    ti.register_tasks(range(length))
    assert -1 in ti._tasks
    start = time.perf_counter()
    ti.register_tasks((length, ))
    duration = time.perf_counter() - start
    assert -1 not in ti._tasks
    assert duration < 0.0005
