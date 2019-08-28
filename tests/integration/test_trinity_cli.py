import signal
import sys
import time

import pexpect
import pytest

from eth.constants import (
    GENESIS_BLOCK_NUMBER,
)

from tests.integration.helpers import (
    run_command_and_detect_errors,
    scan_for_errors,
)

from trinity.config import (
    TrinityConfig,
)
from trinity.constants import (
    ASSETS_DIR,
)
from trinity._utils.async_iter import (
    contains_all
)


ROPSTEN_GENESIS_HASH = '0x41941023680923e0fe4d74a34bdac8141f2540e3ae90623718e47d66d1ca4a2d'
MAINNET_GENESIS_HASH = '0xd4e56740f876aef8c010b86a40d5f56745a118d0906a34e69aec8c0db1cb8fa3'

# IMPORTANT: Test names are intentionally short here because they end up
# in the path name of the isolated Trinity paths that pytest produces for
# us.
# e.g. /tmp/pytest-of-circleci/pytest-0/popen-gw3/test_light_boot_comman0/xdg/mainnet/jsonrpc.ipc)
#
# However, UNIX IPC paths can only be 100 chars which means long paths
# *WILL* break these tests. See: https://unix.stackexchange.com/q/367008


# Great for debugging the AsyncProcessRunner
# @pytest.mark.asyncio
# async def test_ping(async_process_runner):
#     await async_process_runner.run(['ping', 'www.google.de'])
#     assert await contains_all(async_process_runner.stdout, {'bytes from'})


@pytest.mark.parametrize(
    'command',
    (
        ('trinity',),
        ('trinity', '--ropsten',),
    )
)
@pytest.mark.asyncio
async def test_full_boot(async_process_runner, command):
    # Since this short-circuits on sucess, we can set the timeout high.
    # We only hit the timeout if the test fails.
    await async_process_runner.run(command, timeout_sec=120)
    assert await contains_all(async_process_runner.stderr, {
        "Started DB server process",
        "Plugin started: Sync / PeerPool",
        "Running server",
        "IPC started at",
    })


@pytest.mark.parametrize(
    'command',
    (
        ('trinity', '--tx-pool',),
        ('trinity', '--tx-pool', '--ropsten',),
    )
)
@pytest.mark.asyncio
async def test_txpool_full_boot(async_process_runner, command):
    # Since this short-circuits on sucess, we can set the timeout high.
    # We only hit the timeout if the test fails.
    await async_process_runner.run(command, timeout_sec=120)
    assert await contains_all(async_process_runner.stderr, {
        "Started DB server process",
        "Plugin started: Sync / PeerPool",
        "Running Tx Pool",
        "Running server",
        "IPC started at",
    })


@pytest.mark.parametrize(
    'command',
    (
        ('trinity', '--sync-mode=light', '--tx-pool',),
        ('trinity', '--sync-mode=light', '--ropsten', '--tx-pool',),
    )
)
@pytest.mark.asyncio
async def test_txpool_deactivated(async_process_runner, command):
    # Since this short-circuits on sucess, we can set the timeout high.
    # We only hit the timeout if the test fails.
    await async_process_runner.run(command, timeout_sec=120)
    assert await contains_all(async_process_runner.stderr, {
        "Started DB server process",
        "Plugin started: Sync / PeerPool",
        "Transaction pool not available in light mode",
    })


@pytest.mark.parametrize(
    'command',
    (
        ('trinity', '--sync-mode=light',),
        ('trinity', '--sync-mode=light', '--ropsten',),
    )
)
@pytest.mark.asyncio
async def test_light_boot(async_process_runner, command):
    await async_process_runner.run(command, timeout_sec=40)
    assert await contains_all(async_process_runner.stderr, {
        "Started DB server process",
        "Plugin started: Sync / PeerPool",
        "IPC started at",
    })


@pytest.mark.parametrize(
    'command, expected_network_id, expected_genesis_hash',
    (
        (('trinity',), 1, MAINNET_GENESIS_HASH),
        (('trinity', '--ropsten'), 3, ROPSTEN_GENESIS_HASH),
        (
            (
                'trinity',
                f'--genesis={ASSETS_DIR}/eip1085/devnet.json',
                # We don't have a way to refer to the tmp xdg_trinity_root here so we
                # make up this replacement marker
                '--data-dir={trinity_root_path}/devnet',
                '--network-id=5'
            ), 5, '0x065fd78e53dcef113bf9d7732dac7c5132dcf85c9588a454d832722ceb097422'),
    )
)
@pytest.mark.asyncio
async def test_web3(command,
                    expected_network_id,
                    expected_genesis_hash,
                    xdg_trinity_root,
                    async_process_runner):

    command = tuple(
        fragment.replace('{trinity_root_path}', str(xdg_trinity_root))
        for fragment
        in command
    )
    attach_cmd = list(command[1:] + ('attach',))

    await async_process_runner.run(command, timeout_sec=40)
    assert await contains_all(async_process_runner.stderr, {
        "Started DB server process",
        "Plugin started: Sync / PeerPool",
        "IPC started at",
        "Plugin started: JSON-RPC API",
        # Ensure we do not start making requests before Trinity is ready.
        # Waiting for the json-rpc-api event bus to connect to other endpoints
        # seems to be late enough in the process for this to be the case.
        "EventBus Endpoint bjson-rpc-api connecting to other Endpoints",
    })

    attached_trinity = pexpect.spawn('trinity', attach_cmd, logfile=sys.stdout, encoding="utf-8")
    try:
        attached_trinity.expect("An instance of Web3 connected to the running chain")
        attached_trinity.sendline("w3.net.version")
        attached_trinity.expect(f"'{expected_network_id}'")
        attached_trinity.sendline("w3")
        attached_trinity.expect("web3.main.Web3")
        attached_trinity.sendline("w3.eth.getBlock('latest').blockNumber")
        attached_trinity.expect(str(GENESIS_BLOCK_NUMBER))
        attached_trinity.sendline("w3.eth.getBlock('latest').hash")
        attached_trinity.expect(expected_genesis_hash)
    except pexpect.TIMEOUT:
        raise Exception("Trinity attach timeout")
    finally:
        attached_trinity.close()


@pytest.mark.parametrize(
    'command',
    (
        # mainnet
        ('trinity',),
        ('trinity', '--tx-pool',),
        ('trinity', '--sync-mode=light',),
        # ropsten
        ('trinity', '--ropsten',),
        ('trinity', '--ropsten', '--tx-pool',),
        ('trinity', '--sync-mode=light', '--ropsten',),
    )
)
@pytest.mark.asyncio
async def test_does_not_throw(async_process_runner, command):
    # This is our last line of defence. This test basically observes the first
    # 20 seconds of the Trinity boot process and fails if Trinity logs any exceptions
    await run_command_and_detect_errors(async_process_runner, command, 20)


@pytest.mark.parametrize(
    'command,expected_stderr_logs,unexpected_stderr_logs,expected_file_logs,unexpected_file_logs',
    (
        (
            # Default run without any flag
            ('trinity',),
            # Expected stderr logs
            {'Started main process'},
            # Unexpected stderr logs
            {'DiscoveryProtocol  >>> ping'},
            # Expected file logs
            {'Started main process', 'Logging initialized'},
            # Unexpected file logs
            {'DiscoveryProtocol  >>> ping'},
        ),
        (
            # Enable DEBUG2 logs across the board
            ('trinity', '-l=DEBUG2'),
            {'Started main process', 'DiscoveryProtocol  >>> ping'},
            {},
            {'Started main process', 'DiscoveryProtocol  >>> ping'},
            {},
        ),
        (   # Enable DEBUG2 logs for everything except discovery which is reduced to ERROR logs
            ('trinity', '-l=DEBUG2', '-l', 'p2p.discovery=ERROR'),
            {'Started main process', 'ConnectionTrackerServer  Running task <coroutine object'},
            {'DiscoveryProtocol  >>> ping'},
            {'Started main process', 'ConnectionTrackerServer  Running task <coroutine object'},
            {'DiscoveryProtocol  >>> ping'},
        ),
        (
            # Reduce stderr logging to ERROR logs but report DEBUG2 or higher for file logs
            ('trinity', '--stderr-log-level=ERROR', '--file-log-level=DEBUG2',),
            {},
            {'Started main process', 'DiscoveryProtocol  >>> ping'},
            {'Started main process', 'DiscoveryProtocol  >>> ping'},
            {},
        ),
        (
            # Reduce everything to ERROR logs, except discovery that should report DEBUG2 or higher
            ('trinity', '-l=ERROR', '-l', 'p2p.discovery=DEBUG2'),
            {'DiscoveryProtocol  >>> ping'},
            {'Started main process'},
            {},
            {},
            # Increasing per-module log level to a higher value than the general log level does
            # not yet work for file logging. Once https://github.com/ethereum/trinity/issues/689
            # is resolved, the following should work.
            # {'DiscoveryProtocol  >>> ping'},
            # {'Started main process'},
        )
    )
)
@pytest.mark.asyncio
async def test_logger(async_process_runner,
                      command,
                      expected_stderr_logs,
                      unexpected_stderr_logs,
                      expected_file_logs,
                      unexpected_file_logs):

    def contains_substring(iterable, substring):
        return any(substring in x for x in iterable)

    # Saw occasional (<25%, >5%) failures in CI at 30s because of slow machines or bad luck
    await async_process_runner.run(command, timeout_sec=45)

    stderr_logs = []

    # Collect logs up to the point when the sync begins so that we have enough logs for assertions
    marker_seen_at = 0
    async for line in async_process_runner.stderr:
        if marker_seen_at != 0 and time.time() - marker_seen_at > 3:
            break
        if "DiscoveryProtocol" in line:
            marker_seen_at = time.time()
            stderr_logs.append(line)
        else:
            stderr_logs.append(line)

    for log in expected_stderr_logs:
        if not contains_substring(stderr_logs, log):
            assert False, f"Log should contain `{log}` but does not"

    for log in unexpected_stderr_logs:
        if contains_substring(stderr_logs, log):
            assert False, f"Log should not contain `{log}` but does"

    log_file_path = TrinityConfig(app_identifier="eth1", network_id=1).logfile_path
    with open(log_file_path) as log_file:
        file_content = log_file.read()

        for log in expected_file_logs:
            if log not in file_content:
                assert False, f"Logfile should contain `{log}` but does not"

        for log in unexpected_file_logs:
            if log in file_content:
                assert False, f"Logfile should not contain `{log}` but does"


@pytest.mark.parametrize(
    'command',
    (
        ('trinity', ),
    )
)
@pytest.mark.asyncio
# Once we get Trinity to shutdown cleanly, we should remove the xfail so that the test ensures
# ongoing clean exits.
@pytest.mark.xfail
async def test_shutdown(command, async_process_runner):

    async def run_then_shutdown_and_yield_output():
        # This test spins up Trinity, waits until it has started syncing, sends a SIGINT and then
        # tries to scan the entire shutdown process for errors. It needs a little bit more time.
        await async_process_runner.run(command, timeout_sec=50)

        # Somewhat arbitrary but we wait until the syncer starts before we trigger the shutdown.
        # At this point, most of the internals should be set up, leaving us with more room for
        # failure which is what we are looking for in this test.
        trigger = "FastChainBodySyncer"
        triggered = False
        async for line in async_process_runner.stderr:
            if trigger in line:
                triggered = True
                async_process_runner.kill(signal.SIGINT)

            # We are only interested in the output that is created after we initiate the shutdown
            if triggered:
                yield line

    await scan_for_errors(run_then_shutdown_and_yield_output())
