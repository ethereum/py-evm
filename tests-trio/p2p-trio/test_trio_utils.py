import pytest

import trio

from p2p.trio_utils import (
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
