import pytest
from trinity._utils.async_iter import (
    contains_all,
)


@pytest.mark.parametrize(
    'command',
    (
        ('trinity-beacon', 'testnet', "--num=5"),
    )
)
@pytest.mark.asyncio
async def test_directory_generation(async_process_runner, command, tmpdir):
    testnet_path = tmpdir / "testnet"
    testnet_path.mkdir()
    command = command + (f"--network-dir={testnet_path}", )
    await async_process_runner.run(command, timeout_sec=30)
    assert await contains_all(async_process_runner.stderr, {
        "Network generation completed",
    })
