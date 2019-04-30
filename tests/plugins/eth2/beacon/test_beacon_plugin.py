import pytest
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
async def test_plugin_boot(async_process_runner, command):
    await async_process_runner.run(command, timeout_sec=30)
    assert await contains_all(async_process_runner.stderr, {
        "Running server",
    })
