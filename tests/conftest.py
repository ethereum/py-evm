import pytest

import logging
import sys


@pytest.fixture(autouse=True, scope="session")
def vm_logger():
    logger = logging.getLogger('evm')
    #logger.setLevel(logging.INFO)
    #logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)

    return logger
