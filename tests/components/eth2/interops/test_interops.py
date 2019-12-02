import pytest
from trinity.tools.async_process_runner import AsyncProcessRunner
from trinity._utils.async_iter import contains_all


@pytest.mark.parametrize(
    "command",
    (
        (
            "trinity-beacon",
            "-l=DEBUG",
            "interop",
            "--validators=0,1",
            "--start-delay=10",
            "--wipedb",
        ),
    ),
)
@pytest.mark.asyncio
async def test_directory_generation(command, tmpdir):
    async with AsyncProcessRunner.run(command, timeout_sec=60) as runner:
        assert await contains_all(runner.stderr, {"Validator", "BCCReceiveServer"})
