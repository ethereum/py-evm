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
            "--validators=0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15",
            "--start-delay=20",
            "--wipedb",
        ),
    ),
)
@pytest.mark.asyncio
async def test_directory_generation(command, tmpdir):
    async with AsyncProcessRunner.run(command, timeout_sec=30) as runner:
        assert await contains_all(runner.stderr, {"Validator", "BCCReceiveServer"})
