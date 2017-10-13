import logging
import sys

import pytest


@pytest.fixture(autouse=True, scope="session")
def vm_logger():
    logger = logging.getLogger('evm')

    handler = logging.StreamHandler(sys.stdout)

    # level = logging.TRACE
    # level = logging.DEBUG
    level = logging.INFO

    logger.setLevel(level)
    handler.setLevel(level)

    logger.addHandler(handler)

    return logger


# Uncomment this to have logs from tests written to a file.  This is useful for
# debugging when you need to dump the VM output from test runs.
"""
@pytest.yield_fixture(autouse=True)
def vm_file_logger(request):
    import datetime
    import os

    logger = logging.getLogger('evm')

    level = logging.TRACE
    #level = logging.DEBUG
    #level = logging.INFO

    logger.setLevel(level)

    fixture_data = request.getfuncargvalue('fixture_data')
    fixture_path = fixture_data[0]
    logfile_name = 'logs/{0}-{1}.log'.format(
        '-'.join(
            [os.path.basename(fixture_path)] +
            [str(value) for value in fixture_data[1:]]
        ),
        datetime.datetime.now().isoformat(),
    )

    with open(logfile_name, 'w') as logfile:
        handler = logging.StreamHandler(logfile)
        logger.addHandler(handler)
        try:
            yield logger
        finally:
            logger.removeHandler(handler)
"""
