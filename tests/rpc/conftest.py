import asyncio
import os
import pytest
import tempfile
import uuid

from evm.rpc.ipc import (
    start,
)


@pytest.yield_fixture(scope='session')
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='session')
def ipc_pipe():
    tmpdir = tempfile.gettempdir()
    return os.path.join(tmpdir, 'test-%s.ipc' % uuid.uuid4())


@pytest.fixture(scope='session', autouse=True)
def ipc_server(ipc_pipe, event_loop):
    server = start(ipc_pipe, loop=event_loop)

    yield

    server.close()
    event_loop.run_until_complete(server.wait_closed())
    os.remove(ipc_pipe)
