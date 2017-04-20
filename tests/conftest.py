import pytest

import logging
import sys


@pytest.fixture(autouse=True, scope="session")
def vm_logger():
    logger = logging.getLogger('evm')

    handler = logging.StreamHandler(sys.stdout)

    #level = logging.TRACE
    #level = logging.DEBUG
    level = logging.INFO

    logger.setLevel(level)
    handler.setLevel(level)

    logger.addHandler(handler)

    return logger
#
#
#@pytest.yield_fixture(autouse=True)
#def vm_file_logger(request):
#    import datetime
#    logger = logging.getLogger('evm')
#
#    level = logging.TRACE
#    #level = logging.DEBUG
#    #level = logging.INFO
#
#    logger.setLevel(level)
#
#    fixture_name = request.getfuncargvalue('fixture_name')
#    _, _, safe_fixture_name = fixture_name.rpartition('/')
#    logfile_name = 'logs/{0}-{1}.log'.format(safe_fixture_name, datetime.datetime.now().isoformat())
#
#    with open(logfile_name, 'w') as logfile:
#        handler = logging.StreamHandler(logfile)
#        logger.addHandler(handler)
#        try:
#            yield logger
#        finally:
#            logger.removeHandler(handler)
