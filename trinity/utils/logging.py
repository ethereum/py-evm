import logging
from logging import handlers
import sys


def setup_trinity_logging(level):
    from .mp import ctx

    log_queue = ctx.Queue()

    logging.basicConfig(level=level)
    logger = logging.getLogger('trinity')

    handler = logging.StreamHandler(sys.stdout)

    formatter = logging.Formatter(
        '%(levelname)s %(name)s %(asctime)s - %(message)s'
    )
    handler.setFormatter(formatter)

    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    listener = handlers.QueueListener(log_queue, logger)

    return logger, log_queue, listener


def setup_queue_logging(log_queue, level=logging.INFO):
    queue_handler = handlers.QueueHandler(log_queue)
    logging.basicConfig(
        level=level,
        handlers=[queue_handler],
    )

    logger = logging.getLogger()
    logger.debug('Logging initialized')
