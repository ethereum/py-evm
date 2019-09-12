import pytest
from trinity.tools.async_process_runner import AsyncProcessRunner
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
async def test_directory_generation(command, tmpdir):
    testnet_path = tmpdir / "testnet"
    testnet_path.mkdir()
    command = command + (f"--network-dir={testnet_path}", )
    async with AsyncProcessRunner.run(command, timeout_sec=30) as runner:
        assert await contains_all(runner.stderr, {
            "Network generation completed",
        })


@pytest.mark.parametrize(
    'command',
    (
        ('trinity-beacon', 'testnet', "--num=1",),
    )
)
@pytest.mark.asyncio
async def test_missing_genesis_time_arg(command):
    async with AsyncProcessRunner.run(command, timeout_sec=30) as runner:
        assert await contains_all(runner.stderr, {
            "one of the arguments --genesis-delay --genesis-time is required",
        })
