import pytest

import trio

from p2p.trio_utils import (
    every,
    gather,
)


@pytest.mark.trio
async def test_empty_gather():
    result = await gather()
    assert result == ()

    with trio.testing.assert_checkpoints():
        await gather()


@pytest.mark.trio
async def test_gather_sorted(autojump_clock):
    async def f(return_value, sleep_time):
        await trio.sleep(sleep_time)
        return return_value

    results = await gather(
        (f, 0, 0.1),
        (f, 1, 0.2),
        (f, 2, 0.05),
    )
    assert results == (0, 1, 2)


@pytest.mark.trio
async def test_gather_args():
    async def return_args(*args):
        await trio.hazmat.checkpoint()
        return args

    results = await gather(
        return_args,
        (return_args,),
        (return_args, 1, 2, 3)
    )
    assert results == ((), (), (1, 2, 3))


@pytest.mark.trio
async def test_every(autojump_clock):
    start_time = trio.current_time()

    every_generator = every(2, initial_delay=1)

    first_time = await every_generator.__anext__()
    assert first_time == pytest.approx(trio.current_time())
    assert first_time <= trio.current_time()
    assert first_time == pytest.approx(start_time + 1)

    second_time = await every_generator.__anext__()
    assert second_time == pytest.approx(trio.current_time())
    assert second_time == pytest.approx(first_time + 2)

    third_time = await every_generator.__anext__()
    assert third_time == pytest.approx(trio.current_time())
    assert third_time == pytest.approx(first_time + 4)


@pytest.mark.trio
async def test_every_send(autojump_clock):
    start_time = trio.current_time()

    every_generator = every(2, initial_delay=1)

    first_time = await every_generator.__anext__()
    assert first_time == pytest.approx(start_time + 1)

    second_time = await every_generator.asend(3)
    assert second_time == pytest.approx(first_time + 2 + 3)

    third_time = await every_generator.asend(1)
    assert third_time == pytest.approx(second_time + 2 + 1)


@pytest.mark.trio
async def test_every_late(autojump_clock):
    start_time = trio.current_time()

    every_generator = every(2, initial_delay=1)

    first_time = await every_generator.__anext__()
    await trio.sleep(3)

    second_time = await every_generator.__anext__()
    assert second_time == pytest.approx(first_time + 2)
    assert trio.current_time() == pytest.approx(start_time + 1 + 3)

    third_time = await every_generator.__anext__()
    assert third_time == pytest.approx(second_time + 2)
    assert trio.current_time() == pytest.approx(third_time)
