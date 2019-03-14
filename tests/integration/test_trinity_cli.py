import sys
import pexpect
import pytest

from eth_utils import (
    encode_hex,
)
from eth.constants import (
    GENESIS_BLOCK_NUMBER,
    GENESIS_PARENT_HASH,
)

from tests.integration.helpers import (
    run_command_and_detect_errors,
)

from trinity._utils.async_iter import (
    contains_all
)


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
    # UPNP discovery can delay things, we use a timeout longer than the discovery timeout
    await async_process_runner.run(command, timeout_sec=20)
    assert await contains_all(async_process_runner.stderr, {
        "Started DB server process",
        "Started networking process",
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
    # UPNP discovery can delay things, we use a timeout longer than the discovery timeout
    await async_process_runner.run(command, timeout_sec=20)
    assert await contains_all(async_process_runner.stderr, {
        "Started DB server process",
        "Started networking process",
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
    await async_process_runner.run(command, timeout_sec=20)
    assert await contains_all(async_process_runner.stderr, {
        "Started DB server process",
        "Started networking process",
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
    # UPNP discovery can delay things, we use a timeout longer than the discovery timeout
    await async_process_runner.run(command, timeout_sec=20)
    assert await contains_all(async_process_runner.stderr, {
        "Started DB server process",
        "Started networking process",
        "IPC started at",
    })


@pytest.mark.parametrize(
    'command',
    (
        ('trinity', ),
    )
)
@pytest.mark.asyncio
async def test_web3(command, async_process_runner):
    await async_process_runner.run(command, timeout_sec=20)
    assert await contains_all(async_process_runner.stderr, {
        "Started DB server process",
        "Started networking process",
        "IPC started at",
    })

    attached_trinity = pexpect.spawn('trinity', ['attach'], logfile=sys.stdout)
    try:
        attached_trinity.expect("An instance of Web3 connected to the running chain")
        attached_trinity.sendline("w3.net.version")
        attached_trinity.expect("'1'")
        attached_trinity.sendline("w3")
        attached_trinity.expect("web3.main.Web3")
        attached_trinity.sendline("w3.eth.getBlock('latest').blockNumber")
        attached_trinity.expect(str(GENESIS_BLOCK_NUMBER))
        attached_trinity.sendline("w3.eth.getBlock('latest').parentHash")
        attached_trinity.expect(encode_hex(GENESIS_PARENT_HASH))
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
    'command, expected_to_contain_log',
    (
        (('trinity', '-l=DEBUG2'), True),
        # We expect not to contain it because we set the p2p.discovery logger to only log errors
        (('trinity', '-l=DEBUG2', '-l', 'p2p.discovery=ERROR'), False,)
    )
)
@pytest.mark.asyncio
async def test_logger(async_process_runner, command, expected_to_contain_log):
    await async_process_runner.run(command, timeout_sec=20)
    actually_contains_log = await contains_all(async_process_runner.stderr, {
        "DiscoveryProtocol  >>> ping",
    })
    assert actually_contains_log == expected_to_contain_log
