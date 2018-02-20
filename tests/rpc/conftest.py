import asyncio
import os
import pytest
import tempfile
import uuid

from evm.rpc.ipc import (
    start,
)


@pytest.fixture(scope='session')
def event_loop():
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture(scope='session')
def ipc_pipe_path():
    with tempfile.TemporaryDirectory() as temp_dir:
        ipc_path = os.path.join(temp_dir, '{0}.ipc'.format(uuid.uuid4()))
        try:
            yield ipc_path
        finally:
            if os.path.exists(ipc_path):
                os.remove(ipc_path)


@pytest.fixture(scope='session', autouse=True)
def ipc_server(ipc_pipe_path, event_loop):
    '''
    This fixture runs a single RPC server over IPC over
    the course of all tests. It never needs to be actually
    used as a fixture, so it doesn't return (yield) a value.
    '''
    server = start(ipc_pipe_path, loop=event_loop)

    try:
        yield
    finally:
        server.close()
        event_loop.run_until_complete(server.wait_closed())
