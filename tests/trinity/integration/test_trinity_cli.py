import os
import pytest
import shutil

from trinity.tools.async_process_runner import AsyncProcessRunner
from trinity.utils.async_iter import (
    contains_all,
)
from trinity.utils.xdg import (
    get_xdg_runtime_home,
)


XDG_RUNTIME_DIR = os.path.join(get_xdg_runtime_home(), '.test')


@pytest.fixture(scope="function")
def xdg_runtime_dir(monkeypatch):
    assert not os.path.exists(XDG_RUNTIME_DIR)
    os.makedirs(XDG_RUNTIME_DIR)
    assert os.path.exists(XDG_RUNTIME_DIR)
    monkeypatch.setenv('XDG_RUNTIME_DIR', XDG_RUNTIME_DIR)
    try:
        yield XDG_RUNTIME_DIR
    finally:
        assert os.path.exists(XDG_RUNTIME_DIR)
        shutil.rmtree(XDG_RUNTIME_DIR)
        assert not os.path.exists(XDG_RUNTIME_DIR)


# IMPORTANT: Test names are intentionally short here because they end up
# in the path name of the isolated Trinity paths that pytest produces for
# us.
# e.g. /tmp/pytest-of-circleci/pytest-0/popen-gw3/test_light_boot_comman0/xdg/mainnet/jsonrpc.ipc)
#
# However, UNIX IPC paths can only be 100 chars which means long paths
# *WILL* break these tests. See: https://unix.stackexchange.com/q/367008

# This fixture provides a tear down to run after each test that uses it.
# This ensures the AsyncProcessRunner will never leave a process behind
@pytest.fixture(scope="function")
def async_process_runner():
    runner = AsyncProcessRunner(
        # This allows running pytest with -s and observing the output
        debug_fn=lambda line: print(line)
    )
    yield runner
    runner.kill()

# Great for debugging the AsyncProcessRunner
# @pytest.mark.asyncio
# async def test_ping(async_process_runner):
#     await async_process_runner.run(['ping', 'www.google.de'])
#     assert await contains_all(async_process_runner.iterate_stdout(), ['byytes from'])


@pytest.mark.parametrize(
    'command',
    (
        ('trinity',),
        ('trinity', '--ropsten',),
        ('trinity', '--trinity-root-dir', XDG_RUNTIME_DIR,),
        ('trinity', '--trinity-root-dir', XDG_RUNTIME_DIR, '--ropsten',),
    )
)
@pytest.mark.asyncio
async def test_full_boot(async_process_runner, command, xdg_runtime_dir):
    check_command = list(command)
    try:
        # If the --trinity-root-dir is defined, then trinity is expected to start
        check_command.index('--trinity-root-dir')

        # UPNP discovery can delay things, we use a timeout longer than the discovery timeout
        await async_process_runner.run(command, timeout_sec=40)
        assert await contains_all(async_process_runner.stderr, {
            "Started DB server process",
            "Started networking process",
            "Running server",
            "IPC started at",
        })
    except ValueError:
        # If the --trinity-root-dir is NOT defined, then trinity is expected to throw error
        await async_process_runner.run(command, timeout_sec=40)
        assert await contains_all(async_process_runner.stderr, {
            "Please run trinity using --trinity-root-dir param: "
            "trinity --trinity-root-dir <directory>",
        })


@pytest.mark.parametrize(
    'command',
    (
        ('trinity', '--tx-pool',),
        ('trinity', '--tx-pool', '--ropsten',),
        ('trinity', '--trinity-root-dir', XDG_RUNTIME_DIR, '--tx-pool',),
        ('trinity', '--trinity-root-dir', XDG_RUNTIME_DIR, '--tx-pool', '--ropsten',),
    )
)
@pytest.mark.asyncio
async def test_txpool_full_boot(async_process_runner, command, xdg_runtime_dir):
    check_command = list(command)
    try:
        # If the --trinity-root-dir is defined, then trinity is expected to start
        check_command.index('--trinity-root-dir')

        # UPNP discovery can delay things, we use a timeout longer than the discovery timeout
        await async_process_runner.run(command, timeout_sec=40)
        assert await contains_all(async_process_runner.stderr, {
            "Started DB server process",
            "Started networking process",
            "Running Tx Pool",
            "Running server",
            "IPC started at",
        })
    except ValueError:
        # If the --trinity-root-dir is NOT defined, then trinity is expected to throw error
        await async_process_runner.run(command, timeout_sec=40)
        assert await contains_all(async_process_runner.stderr, {
            "Please run trinity using --trinity-root-dir param: "
            "trinity --trinity-root-dir <directory>",
        })


@pytest.mark.parametrize(
    'command',
    (
        ('trinity', '--light', '--tx-pool',),
        ('trinity', '--light', '--ropsten', '--tx-pool',),
    )
)
@pytest.mark.asyncio
async def test_txpool_deactivated(async_process_runner, command):
    await async_process_runner.run(command)
    assert await contains_all(async_process_runner.stderr, {
        "Started DB server process",
        "Started networking process",
        "The transaction pool is not yet available in light mode",
    })


@pytest.mark.parametrize(
    'command',
    (
        ('trinity', '--light',),
        ('trinity', '--light', '--ropsten',),
        ('trinity', '--trinity-root-dir', XDG_RUNTIME_DIR, '--light',),
        ('trinity', '--trinity-root-dir', XDG_RUNTIME_DIR, '--light', '--ropsten',),
    )
)
@pytest.mark.asyncio
async def test_light_boot(async_process_runner, command, xdg_runtime_dir):
    check_command = list(command)
    try:
        # If the --trinity-root-dir is defined, then trinity is expected to start
        check_command.index('--trinity-root-dir')

        # UPNP discovery can delay things, we use a timeout longer than the discovery timeout
        await async_process_runner.run(command, timeout_sec=40)
        assert await contains_all(async_process_runner.stderr, {
            "Started DB server process",
            "Started networking process",
            "IPC started at",
        })
    except ValueError:
        # If the --trinity-root-dir is NOT defined, then trinity is expected to throw error
        await async_process_runner.run(command, timeout_sec=40)
        assert await contains_all(async_process_runner.stderr, {
            "Please run trinity using --trinity-root-dir param: "
            "trinity --trinity-root-dir <directory>",
        })


@pytest.mark.parametrize(
    'command',
    (
        # mainnet
        ('trinity',),
        ('trinity', '--tx-pool',),
        ('trinity', '--light',),
        ('trinity', '--trinity-root-dir', XDG_RUNTIME_DIR,),
        ('trinity', '--trinity-root-dir', XDG_RUNTIME_DIR, '--tx-pool',),
        ('trinity', '--trinity-root-dir', XDG_RUNTIME_DIR, '--light',),
        # ropsten
        ('trinity', '--ropsten',),
        ('trinity', '--ropsten', '--tx-pool',),
        ('trinity', '--light', '--ropsten',),
        ('trinity', '--trinity-root-dir', XDG_RUNTIME_DIR, '--ropsten',),
        ('trinity', '--trinity-root-dir', XDG_RUNTIME_DIR, '--ropsten', '--tx-pool',),
        ('trinity', '--trinity-root-dir', XDG_RUNTIME_DIR, '--light', '--ropsten',),
    )
)
@pytest.mark.asyncio
async def test_does_not_throw(async_process_runner, command, xdg_runtime_dir):
    check_command = list(command)
    try:
        # If the --trinity-root-dir is defined, then trinity is expected to start
        check_command.index('--trinity-root-dir')

        # This is our last line of defence. This test basically observes the first
        # 20 seconds of the Trinity boot process and fails if Trinity logs any exceptions
        lines_since_error = 0
        await async_process_runner.run(command, timeout_sec=20)
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
    except ValueError:
        # If the --trinity-root-dir is NOT defined, then trinity is expected to throw error
        await async_process_runner.run(command, timeout_sec=40)
        assert await contains_all(async_process_runner.stderr, {
            "Please run trinity using --trinity-root-dir param: "
            "trinity --trinity-root-dir <directory>",
        })
