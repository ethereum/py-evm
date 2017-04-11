import pytest

import datetime
import logging
import sys


@pytest.fixture(autouse=True, scope="session")
def vm_logger():
    logger = logging.getLogger('evm')

    handler = logging.StreamHandler(sys.stdout)

    #logger.setLevel(logging.DEBUG)
    #logger.setLevel(logging.DEBUG)
    handler.setLevel(logging.INFO)
    logger.setLevel(logging.INFO)

    logger.addHandler(handler)

    return logger


@pytest.yield_fixture(autouse=True)
def vm_file_logger(request):
    logger = logging.getLogger('evm')

    logger.setLevel(logging.TRACE)

    fixture_name = request.getfuncargvalue('fixture_name')
    logfile_name = 'logs/{0}-{1}.log'.format(fixture_name, datetime.datetime.now().isoformat())

    with open(logfile_name, 'w') as logfile:
        handler = logging.StreamHandler(logfile)
        logger.addHandler(handler)
        try:
            yield logger
        finally:
            logger.removeHandler(handler)
