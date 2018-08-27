import asyncio
from asyncio import (
    Event,
)
from contextlib import contextmanager
import functools
import pytest
import random

from cancel_token import CancelToken, OperationCancelled
from eth_utils import ValidationError
from hypothesis import (
    example,
    given,
    strategies as st,
)

from trinity.utils.datastructures import TaskQueue

DEFAULT_TIMEOUT = 0.05


async def wait(coro, timeout=DEFAULT_TIMEOUT):
    return await asyncio.wait_for(coro, timeout=timeout)


@contextmanager
def trap_operation_cancelled():
    try:
        yield
    except OperationCancelled:
        pass


def run_in_event_loop(async_func):
    @functools.wraps(async_func)
    def wrapped(operations, queue_size, add_size, get_size, event_loop):
        event_loop.run_until_complete(asyncio.ensure_future(
            async_func(operations, queue_size, add_size, get_size, event_loop),
            loop=event_loop,
        ))
    return wrapped


@given(
    operations=st.lists(
        elements=st.tuples(st.integers(min_value=0, max_value=5), st.booleans()),
        min_size=10,
        max_size=30,
    ),
    queue_size=st.integers(min_value=1, max_value=20),
    add_size=st.integers(min_value=1, max_value=20),
    get_size=st.integers(min_value=1, max_value=20),
)
@example(
    # try having two adders alternate a couple times quickly
    operations=[(0, False), (1, False), (0, False), (1, True), (2, False), (2, False), (2, False)],
    queue_size=5,
    add_size=2,
    get_size=5,
)
@run_in_event_loop
async def test_no_asyncio_exception_leaks(operations, queue_size, add_size, get_size, event_loop):
    """
    This could be made much more general, at the cost of simplicity.
    For now, this mimics real usage enough to hopefully catch the big issues.

    Some examples for more generality:

    - different get sizes on each call
    - complete varying amounts of tasks at each call
    """

    async def getter(queue, num_tasks, get_event, complete_event, cancel_token):
        with trap_operation_cancelled():
            # wait to run the get
            await cancel_token.cancellable_wait(get_event.wait())

            batch, tasks = await cancel_token.cancellable_wait(
                queue.get(num_tasks)
            )
            get_event.clear()

            # wait to run the completion
            await cancel_token.cancellable_wait(complete_event.wait())

            queue.complete(batch, tasks)
            complete_event.clear()

    async def adder(queue, add_size, add_event, cancel_token):
        with trap_operation_cancelled():
            # wait to run the add
            await cancel_token.cancellable_wait(add_event.wait())

            await cancel_token.cancellable_wait(
                queue.add(tuple(random.randint(0, 2 ** 32) for _ in range(add_size)))
            )
            add_event.clear()

    async def operation_order(operations, events, cancel_token):
        for operation_id, pause in operations:
            events[operation_id].set()
            if pause:
                await asyncio.sleep(0)

        await asyncio.sleep(0)
        cancel_token.trigger()

    q = TaskQueue(queue_size)
    events = tuple(Event() for _ in range(6))
    add_event, add2_event, get_event, get2_event, complete_event, complete2_event = events
    cancel_token = CancelToken('end test')

    done, pending = await asyncio.wait([
        getter(q, get_size, get_event, complete_event, cancel_token),
        getter(q, get_size, get2_event, complete2_event, cancel_token),
        adder(q, add_size, add_event, cancel_token),
        adder(q, add_size, add2_event, cancel_token),
        operation_order(operations, events, cancel_token),
    ], return_when=asyncio.FIRST_EXCEPTION)

    for task in done:
        exc = task.exception()
        if exc:
            raise exc

    assert not pending


@pytest.mark.asyncio
async def test_queue_size_reset_after_complete():
    q = TaskQueue(maxsize=2)

    await wait(q.add((1, 2)))

    batch, tasks = await wait(q.get())

    # there should not be room to add another task
    try:
        await wait(q.add((3, )))
    except asyncio.TimeoutError:
        pass
    else:
        assert False, "should not be able to add task past maxsize"

    # do imaginary work here, then complete it all

    q.complete(batch, tasks)

    # there should be room to add more now
    await wait(q.add((3, )))


@pytest.mark.asyncio
async def test_queue_contains_task_until_complete():
    q = TaskQueue()

    assert 2 not in q

    await wait(q.add((2, )))

    assert 2 in q

    batch, tasks = await wait(q.get())

    assert 2 in q

    q.complete(batch, tasks)

    assert 2 not in q


@pytest.mark.asyncio
async def test_default_priority_order():
    q = TaskQueue(maxsize=4)
    await wait(q.add((2, 1, 3)))
    (batch, tasks) = await wait(q.get())
    assert tasks == (1, 2, 3)


@pytest.mark.asyncio
async def test_custom_priority_order():
    q = TaskQueue(maxsize=4, order_fn=lambda x: 0 - x)

    await wait(q.add((2, 1, 3)))
    (batch, tasks) = await wait(q.get())
    assert tasks == (3, 2, 1)


@pytest.mark.asyncio
async def test_cannot_add_single_non_tuple_task():
    q = TaskQueue()
    with pytest.raises(ValidationError):
        await wait(q.add(1))


@pytest.mark.asyncio
async def test_unlimited_queue_by_default():
    q = TaskQueue()
    await wait(q.add(tuple(range(100001))))


@pytest.mark.asyncio
async def test_unfinished_tasks_readded():
    q = TaskQueue()
    await wait(q.add((2, 1, 3)))

    batch, tasks = await wait(q.get())

    q.complete(batch, (2, ))

    batch, tasks = await wait(q.get())

    assert tasks == (1, 3)


@pytest.mark.asyncio
async def test_wait_empty_queue():
    q = TaskQueue()
    try:
        await wait(q.get())
    except asyncio.TimeoutError:
        pass
    else:
        assert False, "should not return from get() when nothing is available on queue"


@pytest.mark.asyncio
async def test_cannot_complete_batch_with_wrong_task():
    q = TaskQueue()

    await wait(q.add((1, 2)))

    batch, tasks = await wait(q.get())

    # cannot complete a valid task with a task it wasn't given
    with pytest.raises(ValidationError):
        q.complete(batch, (3, 4))

    # partially invalid completion calls leave the valid task in an incomplete state
    with pytest.raises(ValidationError):
        q.complete(batch, (1, 3))

    assert 1 in q


@pytest.mark.asyncio
async def test_cannot_complete_batch_unless_pending():
    q = TaskQueue()

    await wait(q.add((1, 2)))

    # cannot complete a valid task without a batch id
    with pytest.raises(ValidationError):
        q.complete(None, (1, 2))

    assert 1 in q

    batch, tasks = await wait(q.get())

    # cannot complete a valid task with an invalid batch id
    with pytest.raises(ValidationError):
        q.complete(batch + 1, (1, 2))

    assert 1 in q


@pytest.mark.asyncio
async def test_two_pending_adds_one_release():
    q = TaskQueue(2)

    asyncio.ensure_future(q.add((3, 1, 2)))

    # wait for ^ to run and pause
    await asyncio.sleep(0)
    # note that the highest-priority items are queued first
    assert 1 in q
    assert 2 in q
    assert 3 not in q

    asyncio.ensure_future(q.add((0, 4)))
    # wait for ^ to run and pause
    await asyncio.sleep(0)

    # task consumer 1 completes the first two pending
    batch, tasks = await wait(q.get())
    assert tasks == (1, 2)
    q.complete(batch, tasks)

    # task consumer 2 gets the next two, in priority order
    batch, tasks = await wait(q.get())
    assert len(tasks) in {0, 1}

    if len(tasks) == 1:
        _, tasks2 = await wait(q.get())
        all_tasks = tuple(sorted(tasks + tasks2))
    elif len(tasks) == 2:
        all_tasks = tasks

    assert all_tasks == (0, 3)

    # clean up, so the pending get() call can complete
    q.complete(batch, tasks)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'start_tasks, get_max, expected, remainder',
    (
        ((4, 3, 2, 1), 5, (1, 2, 3, 4), None),
        ((4, 3, 2, 1), 4, (1, 2, 3, 4), None),
        ((4, 3, 2, 1), 3, (1, 2, 3), (4, )),
    ),
)
async def test_queue_get_cap(start_tasks, get_max, expected, remainder):
    q = TaskQueue()

    await wait(q.add(start_tasks))

    batch, tasks = await wait(q.get(get_max))
    assert tasks == expected

    if remainder:
        _, tasks2 = await wait(q.get())
        assert tasks2 == remainder
    else:
        try:
            _, tasks2 = await wait(q.get())
        except asyncio.TimeoutError:
            pass
        else:
            assert False, f"No more tasks to get, but got {tasks2!r}"


@pytest.mark.asyncio
async def test_cannot_readd_same_task():
    q = TaskQueue()
    await q.add((1, 2))
    with pytest.raises(ValidationError):
        await q.add((2,))


@pytest.mark.parametrize('get_size', (1, None))
def test_get_nowait_queuefull(get_size):
    q = TaskQueue()
    with pytest.raises(asyncio.QueueFull):
        q.get_nowait(get_size)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'tasks, get_size, expected_tasks',
    (
        ((3, 2), 1, (2, )),
    ),
)
async def test_get_nowait(tasks, get_size, expected_tasks):
    q = TaskQueue()
    await q.add(tasks)

    batch, tasks = q.get_nowait(get_size)

    assert tasks == expected_tasks

    q.complete(batch, tasks)

    assert all(task not in q for task in tasks)
