import pytest
from trinity._utils.async_iter import (
    contains_all
)


@pytest.mark.parametrize(
    'command',
    (
        ('trinity-beacon',),
    )
)
@pytest.mark.asyncio
async def test_plugin_boot(async_process_runner, command):
    await async_process_runner.run(command, timeout_sec=30)
    assert await contains_all(async_process_runner.stderr, {
        "Running server",
    })
