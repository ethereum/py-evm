import pytest
from trinity.tools.async_process_runner import AsyncProcessRunner
from trinity._utils.async_iter import (
    contains_all
)


# FIXME: this test should not be skipped after genesis json is added
@pytest.mark.skip(reason="need genesis json to initialize `genesis_data`")
@pytest.mark.parametrize(
    'command',
    (
        ('trinity-beacon',),
    )
)
@pytest.mark.asyncio
async def test_component_boot(command):
    async with AsyncProcessRunner.run(command, timeout_sec=30) as runner:
        assert await contains_all(runner.stderr, {
            "Running server",
        })
