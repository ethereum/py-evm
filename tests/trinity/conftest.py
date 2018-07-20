import asyncio
import os
from pathlib import Path
import pytest
import tempfile
import uuid

from p2p.peer import PeerPool
from p2p.server import (
    Server
)

from trinity.rpc.main import (
    RPCServer,
)
from trinity.rpc.ipc import (
    IPCServer,
)
from trinity.utils.xdg import (
    get_xdg_trinity_root,
)
from trinity.utils.filesystem import (
    is_under_path,
)


@pytest.fixture(autouse=True)
def xdg_trinity_root(monkeypatch, tmpdir):
    """
    Ensure proper test isolation as well as protecting the real directories.
    """
    dir_path = tmpdir.mkdir('trinity')
    monkeypatch.setenv('XDG_TRINITY_ROOT', str(dir_path))

    assert not is_under_path(os.path.expandvars('$HOME'), get_xdg_trinity_root())

    return str(dir_path)


@pytest.fixture(scope='session')
def event_loop():
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture(scope='session')
def jsonrpc_ipc_pipe_path():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir) / '{0}.ipc'.format(uuid.uuid4())


@pytest.fixture
def p2p_server(monkeypatch, jsonrpc_ipc_pipe_path):
    monkeypatch.setattr(
        Server, '_make_peer_pool', lambda s: PeerPool(None, None, None, None, None, None))
    return Server(None, None, None, None, None, None, None)


@pytest.mark.asyncio
@pytest.fixture
async def ipc_server(
        monkeypatch,
        p2p_server,
        jsonrpc_ipc_pipe_path,
        event_loop,
        chain_with_block_validation):
    '''
    This fixture runs a single RPC server over IPC over
    the course of all tests. It never needs to be actually
    used as a fixture, so it doesn't return (yield) a value.
    '''

    rpc = RPCServer(chain_with_block_validation, p2p_server.peer_pool)
    ipc_server = IPCServer(rpc, jsonrpc_ipc_pipe_path, loop=event_loop)

    asyncio.ensure_future(ipc_server.run(), loop=event_loop)

    try:
        yield
    finally:
        await ipc_server.cancel()
