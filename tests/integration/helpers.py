async def run_command_and_detect_errors(async_process_runner, command, time):
    """
    Run the given ``command`` on the given ``async_process_runner`` for ``time`` seconds and
    throw an Exception in case any unresolved Exceptions are detected in the output of the command.
    """
    lines_since_error = 0
    await async_process_runner.run(command, timeout_sec=time)
    async for line in async_process_runner.stderr:

        # We detect errors by some string at the beginning of the Traceback and keep
        # counting lines from there to be able to read and report more valuable info
        if "Traceback (most recent call last)" in line and lines_since_error == 0:
            lines_since_error = 1
        elif lines_since_error > 0:
            lines_since_error += 1

        # Keep on listening for output for a maxmimum of 100 lines after the error
        if lines_since_error >= 100:
            break

    if lines_since_error > 0:
        raise Exception("Exception during Trinity boot detected")
