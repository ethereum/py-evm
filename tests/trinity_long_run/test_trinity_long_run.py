import pytest

from tests.integration.helpers import (
    run_command_and_detect_errors,
)


@pytest.mark.parametrize(
    'command',
    (
        # ropsten
        ('trinity', '--ropsten',),
    )
)
@pytest.mark.asyncio
async def test_does_not_throw_errors_on_long_run(command):
    # Ensure that no errors are thrown when trinity is run for 90 seconds
    await run_command_and_detect_errors(command, 90)
