import asyncio
import logging
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time

import pytest
import rlp
from eth_utils import (
    decode_hex,
    encode_hex,
    to_text,
)

from eth_hash.auto import keccak

from eth.chains.ropsten import (
    ROPSTEN_GENESIS_HEADER,
    ROPSTEN_VM_CONFIGURATION,
)
from eth.db.atomic import AtomicDB

from p2p import ecies
from p2p.constants import DEVP2P_V5
from p2p.kademlia import Node

from trinity._utils.ipc import kill_popen_gracefully
from trinity.constants import ROPSTEN_NETWORK_ID
from trinity.db.eth1.chain import AsyncChainDB
from trinity.db.eth1.header import AsyncHeaderDB
from trinity.protocol.common.context import ChainContext
from trinity.protocol.les.peer import LESPeerPool
from trinity.sync.light.chain import LightChainSyncer
from trinity.sync.light.service import LightPeerChain
from trinity.tools.chain import AsyncRopstenChain

from tests.core.integration_test_helpers import (
    connect_to_peers_loop,
)


@pytest.fixture
async def geth_port(unused_tcp_port):
    return unused_tcp_port


@pytest.fixture
def geth_datadir():
    fixture_datadir = Path(__file__).parent / 'fixtures' / 'geth_lightchain_datadir'
    with tempfile.TemporaryDirectory() as temp_dir:
        datadir = Path(temp_dir) / 'geth'
        shutil.copytree(fixture_datadir, datadir)
        yield datadir


@pytest.fixture
def enode(geth_port):
    return (
        "enode://"
        "96b3d566ca9b9db43e4e5efa2e17fb95f7ddfe72981aadadda2080b4cab23c4d863acf31d715422cd87bec4faf3c8ad2e74da0065332d870b6bd07d0433bec71"  # noqa: E501
        "@127.0.0.1:%d" % geth_port
    )


@pytest.fixture
def geth_ipc_path(geth_datadir):
    return geth_datadir / 'geth.ipc'


@pytest.fixture
def geth_binary():
    path_result = subprocess.check_output('which geth', shell=True)
    path = path_result.decode().strip('\n')
    if not path:
        raise EnvironmentError("geth must be installed, but was not found")
    else:
        return path


@pytest.fixture
def geth_command_arguments(geth_binary, geth_ipc_path, geth_datadir, geth_port):
    return (
        geth_binary,
        '--testnet',
        '--datadir', str(geth_datadir),
        '--ipcpath', geth_ipc_path,
        '--lightserv', '90',
        '--nodiscover',
        '--fakepow',
        '--port', str(geth_port),
    )


@pytest.fixture
def geth_process(geth_command_arguments):
    proc = subprocess.Popen(
        geth_command_arguments,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
    )
    logging.warning('start geth: %r' % (geth_command_arguments,))
    try:
        yield proc
    finally:
        logging.warning('shutting down geth')
        kill_popen_gracefully(proc, logging.getLogger('tests.integration.lightchain'))
        output, errors = proc.communicate()
        logging.warning(
            "Geth Process Exited:\n"
            "stdout:{0}\n\n"
            "stderr:{1}\n\n".format(
                to_text(output),
                to_text(errors),
            )
        )


def wait_for_socket(ipc_path, timeout=10):
    start = time.monotonic()
    while time.monotonic() < start + timeout:
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(str(ipc_path))
            sock.settimeout(timeout)
        except (FileNotFoundError, socket.error):
            time.sleep(0.01)
        else:
            break


@pytest.mark.asyncio
async def test_lightchain_integration(
        request,
        event_loop,
        caplog,
        geth_ipc_path,
        enode,
        geth_process):
    """Test LightChainSyncer/LightPeerChain against a running geth instance.

    In order to run this manually, you can use `tox -e py36-lightchain_integration` or:

        pytest --integration --capture=no tests/integration/test_lightchain_integration.py

    The fixture for this test was generated with:

        geth --testnet --syncmode full

    It only needs the first 11 blocks for this test to succeed.
    """
    if not pytest.config.getoption("--integration"):
        pytest.skip("Not asked to run integration tests")

    # will almost certainly want verbose logging in a failure
    caplog.set_level(logging.DEBUG)

    # make sure geth has been launched
    wait_for_socket(geth_ipc_path)

    remote = Node.from_uri(enode)
    base_db = AtomicDB()
    chaindb = AsyncChainDB(base_db)
    chaindb.persist_header(ROPSTEN_GENESIS_HEADER)
    headerdb = AsyncHeaderDB(base_db)
    context = ChainContext(
        headerdb=headerdb,
        network_id=ROPSTEN_NETWORK_ID,
        vm_configuration=ROPSTEN_VM_CONFIGURATION,
        client_version_string='trinity-test',
        listen_port=30303,
        p2p_version=DEVP2P_V5,
    )
    peer_pool = LESPeerPool(
        privkey=ecies.generate_privkey(),
        context=context,
    )
    chain = AsyncRopstenChain(base_db)
    syncer = LightChainSyncer(chain, chaindb, peer_pool)
    syncer.min_peers_to_sync = 1
    peer_chain = LightPeerChain(headerdb, peer_pool)

    asyncio.ensure_future(peer_pool.run())
    asyncio.ensure_future(connect_to_peers_loop(peer_pool, tuple([remote])))
    asyncio.ensure_future(peer_chain.run())
    asyncio.ensure_future(syncer.run())
    await asyncio.sleep(0)  # Yield control to give the LightChainSyncer a chance to start

    def finalizer():
        event_loop.run_until_complete(peer_pool.cancel())
        event_loop.run_until_complete(peer_chain.cancel())
        event_loop.run_until_complete(syncer.cancel())

    request.addfinalizer(finalizer)

    n = 11

    # Wait for the chain to sync a few headers.
    async def wait_for_header_sync(block_number):
        while headerdb.get_canonical_head().block_number < block_number:
            await asyncio.sleep(0.1)
    await asyncio.wait_for(wait_for_header_sync(n), 5)

    # https://ropsten.etherscan.io/block/11
    header = headerdb.get_canonical_block_header_by_number(n)
    body = await peer_chain.coro_get_block_body_by_hash(header.hash)
    assert len(body['transactions']) == 15

    receipts = await peer_chain.coro_get_receipts(header.hash)
    assert len(receipts) == 15
    assert encode_hex(keccak(rlp.encode(receipts[0]))) == (
        '0xf709ed2c57efc18a1675e8c740f3294c9e2cb36ba7bb3b89d3ab4c8fef9d8860')

    assert len(peer_pool) == 1
    peer = peer_pool.highest_td_peer
    head = await peer_chain.coro_get_block_header_by_hash(peer.head_hash)

    # In order to answer queries for contract code, geth needs the state trie entry for the block
    # we specify in the query, but because of fast sync we can only assume it has that for recent
    # blocks, so we use the current head to lookup the code for the contract below.
    # https://ropsten.etherscan.io/address/0x95a48dca999c89e4e284930d9b9af973a7481287
    contract_addr = decode_hex('0x8B09D9ac6A4F7778fCb22852e879C7F3B2bEeF81')
    contract_code = await peer_chain.coro_get_contract_code(head.hash, contract_addr)
    assert encode_hex(contract_code) == '0x600060006000600060006000356000f1'

    account = await peer_chain.coro_get_account(head.hash, contract_addr)
    assert account.code_hash == keccak(contract_code)
    assert account.balance == 0
