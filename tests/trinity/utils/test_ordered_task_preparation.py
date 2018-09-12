import asyncio
from enum import Enum, auto

from eth_utils import (
    ValidationError,
)
from eth_utils.toolz import identity
import pytest

from trinity.utils.datastructures import (
    OrderedTaskPreparation,
)

DEFAULT_TIMEOUT = 0.05


async def wait(coro, timeout=DEFAULT_TIMEOUT):
    return await asyncio.wait_for(coro, timeout=timeout)


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
    with pytest.raises(ValidationError):
        # this depends on 3
        ti.register_tasks((14, ))

    # test the same concept, but after pruning more than just the starting task...
    ti.register_tasks((7, ))
    ti.finish_prereq(OnePrereq.one, (7, ))

    ti.register_tasks((16, ))
    ti.register_tasks((17, ))
    with pytest.raises(ValidationError):
        ti.register_tasks((15, ))


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


def test_empty_enum():

    class NoPrerequisites(Enum):
        pass

    with pytest.raises(ValidationError):
        OrderedTaskPreparation(NoPrerequisites, identity, lambda x: x - 1)
