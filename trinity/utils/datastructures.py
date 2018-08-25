from asyncio import (
    Lock,
    PriorityQueue,
    Queue,
    QueueFull,
    BoundedSemaphore,
)
from itertools import count
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Set,
    Tuple,
    TypeVar,
)

from eth_utils import (
    ValidationError,
)
from eth_utils.toolz import identity

TTask = TypeVar('TTask')


class TaskQueue(Generic[TTask]):
    """
    TaskQueue keeps priority-order track of pending tasks, with a limit on number pending.

    A producer of tasks will insert pending tasks with await add(), which will not return until
    all tasks have been added to the queue.

    A task consumer calls await get() to retrieve tasks to attempt. Tasks will be returned in
    priority order. If no tasks are pending, get()
    will pause until at least one is available. Only one consumer will have a task "checked out"
    from get() at a time.

    After tasks are successfully completed, the consumer will call complete() to remove them from
    the queue. The consumer doesn't need to complete all tasks, but any uncompleted tasks will be
    considered abandoned. Another consumer can pick it up at the next get() call.
    """

    # a function that determines the priority order (lower int is higher priority)
    _order_fn: Callable[[TTask], Any]

    # batches of tasks that have been started but not completed
    _in_progress: Dict[int, Tuple[TTask, ...]]

    # all tasks that have been placed in the queue and have not been started
    _open_queue: 'PriorityQueue[Tuple[Any, TTask]]'

    # all tasks that have been placed in the queue and have not been completed
    _tasks: Set[TTask]

    def __init__(
            self,
            maxsize: int = 0,
            order_fn: Callable[[TTask], Any] = identity,
            *,
            loop=None) -> None:
        self._maxsize = maxsize
        self._full_lock = Lock(loop=loop)
        self._open_queue = PriorityQueue(maxsize, loop=loop)
        self._order_fn = order_fn
        self._id_generator = count()
        self._tasks = set()
        self._in_progress = {}

    async def add(self, tasks: Tuple[TTask, ...]) -> None:
        """
        add() will insert as many tasks as can be inserted until the queue fills up.
        Then it will pause until the queue is no longer full, and continue adding tasks.
        It will finally return when all tasks have been inserted.
        """
        if not isinstance(tasks, tuple):
            raise ValidationError(f"must pass a tuple of tasks to add(), but got {tasks!r}")

        # make sure to insert the highest-priority items first, in case queue fills up
        remaining = tuple(sorted((self._order_fn(task), task) for task in tasks))

        while remaining:
            num_tasks = len(self._tasks)

            if self._maxsize <= 0:
                # no cap at all, immediately insert all tasks
                open_slots = len(remaining)
            elif num_tasks < self._maxsize:
                # there is room to add at least one more task
                open_slots = self._maxsize - num_tasks
            else:
                # wait until there is room in the queue
                await self._full_lock.acquire()

                # the current number of tasks has changed, can't reuse num_tasks
                num_tasks = len(self._tasks)
                open_slots = self._maxsize - num_tasks

            queueing, remaining = remaining[:open_slots], remaining[open_slots:]

            for task in queueing:
                # There will always be room in _open_queue until _maxsize is reached
                try:
                    self._open_queue.put_nowait(task)
                except QueueFull:
                    task_idx = queueing.index(task)
                    # TODO remove once this bug is tracked down
                    import logging; logging.error(
                        'TaskQueue unsuccessful in adding task %r because qsize=%d, '
                        'num_tasks=%d, _maxsize=%d, open_slots=%d, num queueing=%d, '
                        'len(_tasks)=%d, task_idx=%d, queuing=%r',
                        task,
                        self._open_queue.qsize(),
                        num_tasks,
                        self._maxsize,
                        open_slots,
                        len(queueing),
                        len(self._tasks),
                        task_idx,
                        queueing,
                    )
                    raise

            unranked_queued = tuple(task for _rank, task in queueing)
            self._tasks.update(unranked_queued)

            if self._full_lock.locked() and len(self._tasks) < self._maxsize:
                self._full_lock.release()

    async def get(self, max_results: int = None) -> Tuple[int, Tuple[TTask, ...]]:
        """Get all the currently pending tasks. If no tasks pending, wait until one is"""
        # TODO add argument to optionally limit the number of tasks retrieved
        if max_results is not None and max_results < 1:
            raise ValidationError("Must request at least one task to process, not {max_results!r}")

        # if the queue is empty, wait until at least one item is available
        queue = self._open_queue
        if queue.empty():
            first_task = await queue.get()
        else:
            first_task = queue.get_nowait()

        available = queue.qsize()

        # In order to return from get() as soon as possible, never await again.
        # Instead, take only the tasks that are already waiting.

        # How many results past the first one do we want?
        if max_results is None:
            more_tasks_to_return = available
        else:
            more_tasks_to_return = min((available, max_results - 1))

        # Combine the remaining tasks with the first task we already pulled.
        ranked_tasks = (first_task, ) + tuple(
            queue.get_nowait() for _ in range(more_tasks_to_return)
        )

        # strip out the rank value used internally, for sorting in the priority queue
        unranked_tasks = tuple(task for _rank, task in ranked_tasks)

        # save the batch for later, so uncompleted tasks can be inferred
        next_id = next(self._id_generator)
        self._in_progress[next_id] = unranked_tasks

        return (next_id, unranked_tasks)

    def complete(self, batch_id: int, completed: Tuple[TTask, ...]) -> None:
        if batch_id not in self._in_progress:
            raise ValidationError(f"batch id {batch_id} not recognized, with tasks {completed!r}")

        attempted = self._in_progress.pop(batch_id)

        remaining = set(attempted).difference(completed)

        for task in remaining:
            # These tasks are already counted in the total task count, so there will be room
            self._open_queue.put_nowait((self._order_fn(task), task))

        self._tasks.difference_update(completed)

        if self._full_lock.locked() and len(self._tasks) < self._maxsize:
            self._full_lock.release()

    def __contains__(self, task: TTask) -> bool:
        """Determine if a task has been added and not yet completed"""
        return task in self._tasks
