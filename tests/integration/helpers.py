from trinity.tools.async_process_runner import AsyncProcessRunner


async def run_command_and_detect_errors(command, time):
    """
    Run the given ``command`` on the given ``async_process_runner`` for ``time`` seconds and
    throw an Exception in case any unresolved Exceptions are detected in the output of the command.
    """
    async with AsyncProcessRunner.run(command, timeout_sec=time) as runner:
        await scan_for_errors(runner.stderr)


async def scan_for_errors(async_iterable):
    """
    Consume the output produced by the async iterable and throw if it contains hints of an
    uncaught exception.
    """

    error_trigger = (
        "Exception ignored",
        "exception was never retrieved",
        "finished unexpectedly",
        "ResourceWarning",
        "Task was destroyed but it is pending",
        "Traceback (most recent call last)",
    )

    lines_since_error = 0
    last_error = None
    async for line in async_iterable:

        # We detect errors by some string at the beginning of the Traceback and keep
        # counting lines from there to be able to read and report more valuable info
        if any(trigger in line for trigger in error_trigger) and lines_since_error == 0:
            lines_since_error = 1
            last_error = line
        elif lines_since_error > 0:
            lines_since_error += 1

        # Keep on listening for output for a maxmimum of 100 lines after the error
        if lines_since_error >= 100:
            break

    if last_error is not None:
        raise Exception(f"Exception during Trinity boot detected: {last_error}")
