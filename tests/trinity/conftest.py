import asyncio
import os
from pathlib import Path
import pytest
import tempfile
import uuid

from lahja import (
    EventBus,
)

from eth.chains import (
    Chain,
)

from trinity.chains.coro import (
    AsyncChainMixin,
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
from tests.conftest import (
    _chain_with_block_validation,
)


class TestAsyncChain(Chain, AsyncChainMixin):
    pass


def pytest_addoption(parser):
    parser.addoption("--enode", type=str, required=False)
    parser.addoption("--integration", action="store_true", default=False)


@pytest.fixture(autouse=True)
def xdg_trinity_root(monkeypatch, tmpdir):
    """
    Ensure proper test isolation as well as protecting the real directories.
    """
    dir_path = tmpdir.mkdir('trinity')
    monkeypatch.setenv('XDG_TRINITY_ROOT', str(dir_path))

    assert not is_under_path(os.path.expandvars('$HOME'), get_xdg_trinity_root())

    return Path(str(dir_path))


@pytest.fixture(scope='session')
def event_loop():
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture(scope='module')
def event_bus(event_loop):
    bus = EventBus()
    endpoint = bus.create_endpoint('test')
    bus.start(event_loop)
    endpoint.connect(event_loop)
    try:
        yield endpoint
    finally:
        endpoint.stop()
        bus.stop()


@pytest.fixture(scope='session')
def jsonrpc_ipc_pipe_path():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir) / '{0}.ipc'.format(uuid.uuid4())


@pytest.fixture
def chain_with_block_validation(base_db, genesis_state):
    return _chain_with_block_validation(base_db, genesis_state, TestAsyncChain)


@pytest.mark.asyncio
@pytest.fixture
async def ipc_server(
        monkeypatch,
        event_bus,
        jsonrpc_ipc_pipe_path,
        event_loop,
        chain_with_block_validation):
    '''
    This fixture runs a single RPC server over IPC over
    the course of all tests. It yields the IPC server only for monkeypatching purposes
    '''
    rpc = RPCServer(chain_with_block_validation, event_bus)
    ipc_server = IPCServer(rpc, jsonrpc_ipc_pipe_path, loop=event_loop)

    asyncio.ensure_future(ipc_server.run(), loop=event_loop)

    try:
        yield ipc_server
    finally:
        await ipc_server.cancel()
