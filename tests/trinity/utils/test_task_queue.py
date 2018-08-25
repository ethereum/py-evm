import asyncio
import pytest

from eth_utils import ValidationError

from trinity.utils.datastructures import TaskQueue


async def wait(coro, timeout=0.05):
    return await asyncio.wait_for(coro, timeout=timeout)


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
    q = TaskQueue(maxsize=4, order_fn=lambda x: 0-x)

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
        batch2, tasks2 = await wait(q.get())
        all_tasks = tuple(sorted(tasks + tasks2))
    elif len(tasks) == 2:
        batch2 = None
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
        batch2, tasks2 = await wait(q.get())
        assert tasks2 == remainder
    else:
        try:
            batch2, tasks2 = await wait(q.get())
        except asyncio.TimeoutError:
            pass
        else:
            assert False, f"No more tasks to get, but got {tasks2!r}"
