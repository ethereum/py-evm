import pytest
from trinity._utils.async_iter import (
    contains_all,
)


@pytest.mark.parametrize(
    'command',
    (
        ('trinity-beacon', 'testnet', "--num=1", "--genesis-delay=10"),
        ('trinity-beacon', 'testnet', "--num=1", "--genesis-time=1559315137"),
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


@pytest.mark.parametrize(
    'command',
    (
        ('trinity-beacon', 'testnet', "--num=1",),
    )
)
@pytest.mark.asyncio
async def test_missing_genesis_time_arg(async_process_runner, command):
    await async_process_runner.run(command, timeout_sec=30)
    assert await contains_all(async_process_runner.stderr, {
        "one of the arguments --genesis-delay --genesis-time is required",
    })
