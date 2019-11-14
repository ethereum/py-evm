import tempfile
import logging
from multiprocessing import Process
from pathlib import Path
import uuid

import pytest

from trinity._utils.logging import IPCListener, IPCHandler


@pytest.fixture
def ipc_path():
    with tempfile.TemporaryDirectory() as dir:
        yield Path(dir) / "logging.ipc"


def test_queued_logging(ipc_path):
    class HandlerForTest(logging.Handler):
        def __init__(self):
            self.logs = []
            super().__init__()

        def handle(self, record):
            self.logs.append(record)

    def do_other_process_logging(ipc_path):
        queue_handler = IPCHandler.connect(ipc_path)
        queue_handler.setLevel(logging.DEBUG)
        logger = logging.getLogger(str(uuid.uuid4()))
        logger.addHandler(queue_handler)
        logger.setLevel(logging.DEBUG)

        logger.error('error log')
        logger.info('info log')
        logger.debug('debug log')

        queue_handler.close()

    proc = Process(target=do_other_process_logging, args=(ipc_path,))

    logger = logging.getLogger(str(uuid.uuid4()))

    handler = HandlerForTest()
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    queue_listener = IPCListener(handler)

    with queue_listener.run(ipc_path):
        assert len(handler.logs) == 0
        proc.start()
        proc.join()
        assert len(handler.logs) == 3

    error_log, info_log, debug_log = handler.logs

    assert 'error log' in error_log.message
    assert 'info log' in info_log.message
    assert 'debug log' in debug_log.message
