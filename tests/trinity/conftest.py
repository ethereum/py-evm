import asyncio
import os
import pytest
import tempfile
import uuid

from evm import constants as evm_constants

from trinity.rpc.main import (
    RPCServer,
)
from trinity.rpc.ipc import (
    IPCServer,
)
from trinity.utils.xdg import (
    XDG_DATA_HOME,
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
    dir_path = tmpdir.mkdir('xdg_trinity_root')
    monkeypatch.setenv('XDG_TRINITY_ROOT', str(dir_path))

    assert not is_under_path(XDG_DATA_HOME, get_xdg_trinity_root())

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
        ipc_path = os.path.join(temp_dir, '{0}.ipc'.format(uuid.uuid4()))
        try:
            yield ipc_path
        finally:
            if os.path.exists(ipc_path):
                os.remove(ipc_path)


@pytest.fixture(scope='session')
def ipc_server(jsonrpc_ipc_pipe_path, event_loop):
    '''
    This fixture runs a single RPC server over IPC over
    the course of all tests. It never needs to be actually
    used as a fixture, so it doesn't return (yield) a value.
    '''
    rpc = RPCServer(None)
    ipc_server = IPCServer(rpc, jsonrpc_ipc_pipe_path)

    asyncio.ensure_future(ipc_server.run(loop=event_loop), loop=event_loop)

    try:
        yield
    finally:
        event_loop.run_until_complete(ipc_server.stop())


@pytest.fixture
def custom_network_genesis_params():
    return dict(
        difficulty=12345,
        extra_data=b"\xde\xad\xbe\xef" * 8,
        gas_limit=1234567,
        gas_used=0,
        bloom=0,
        mix_hash=evm_constants.ZERO_HASH32,
        nonce=evm_constants.GENESIS_NONCE,
        block_number=0,
        parent_hash=evm_constants.ZERO_HASH32,
        receipt_root=evm_constants.BLANK_ROOT_HASH,
        uncles_hash=evm_constants.EMPTY_UNCLE_HASH,
        state_root=evm_constants.BLANK_ROOT_HASH,
        timestamp=0,
        transaction_root=evm_constants.BLANK_ROOT_HASH,
    )
