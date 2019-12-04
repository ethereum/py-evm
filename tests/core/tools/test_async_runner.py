import pytest

from trinity._utils.async_iter import contains_all
from trinity.tools.async_process_runner import AsyncProcessRunner


@pytest.mark.parametrize("command", (("yes",),))
@pytest.mark.asyncio
async def test_async_process_runner(command):
    async with AsyncProcessRunner.run(command, timeout_sec=1) as runner:
        assert not await contains_all(runner.stderr, {"Inexistent keyword"})
        return
    raise AssertionError("Unreachable: AsyncProcessRunner skipped the return statement")
