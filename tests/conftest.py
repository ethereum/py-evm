import pytest

import logging
import sys


@pytest.fixture(autouse=True, scope="session")
def vm_logger():
    logger = logging.getLogger('evm')
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)

    return logger
