import asyncio
import os
import pytest
import tempfile
from threading import Thread
import time
import uuid

from evm.rpc.ipc import (
    get_test_chain,
    start,
)


@pytest.fixture(scope='session')
def ipc_pipe():
    tmpdir = tempfile.gettempdir()
    return os.path.join(tmpdir, 'test-%s.ipc' % uuid.uuid4())


@pytest.fixture(scope='session', autouse=True)
def ipc_server(ipc_pipe):
    def serve_test_data():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        start(ipc_pipe, get_test_chain())
    thread = Thread(target=serve_test_data, daemon=True)
    thread.start()

    for _ in range(100):
        if os.path.exists(ipc_pipe):
            break
        time.sleep(0.01)
