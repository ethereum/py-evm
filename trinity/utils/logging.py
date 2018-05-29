import functools
import logging
from logging import Logger
from logging.handlers import (
    QueueListener,
    QueueHandler,
    RotatingFileHandler,
)
from multiprocessing import Queue
import os
import sys

from cytoolz import dissoc

from typing import Tuple, Callable

from trinity.config import (
    ChainConfig,
)

LOG_BACKUP_COUNT = 10
LOG_MAX_MB = 5


def setup_trinity_logging(
        chain_config: ChainConfig,
        level: int) -> Tuple[Logger, Queue, QueueListener]:
    from .mp import ctx

    log_queue = ctx.Queue()

    logger = logging.getLogger('trinity')
    logger.setLevel(logging.DEBUG)

    handler_stream = logging.StreamHandler(sys.stdout)
    handler_file = RotatingFileHandler(
        str(chain_config.logfile_path),
        maxBytes=(10000000 * LOG_MAX_MB),
        backupCount=LOG_BACKUP_COUNT
    )

    handler_stream.setLevel(level)
    handler_file.setLevel(logging.DEBUG)

    # TODO: allow configuring `detailed` logging
    formatter = logging.Formatter(
        fmt='%(levelname)8s  %(asctime)s  %(module)10s  %(message)s',
        datefmt='%m-%d %H:%M:%S'
    )
    handler_stream.setFormatter(formatter)
    handler_file.setFormatter(formatter)

    logger.addHandler(handler_stream)
    logger.addHandler(handler_file)

    logger.info("Trinity DEBUG log file is created at %s", str(chain_config.logfile_path))
    logger.debug('Logging initialized: PID=%s', os.getpid())

    listener = QueueListener(
        log_queue,
        handler_stream,
        handler_file,
        respect_handler_level=True,
    )

    return logger, log_queue, listener


def setup_queue_logging(log_queue: Queue, level: int) -> None:
    queue_handler = QueueHandler(log_queue)
    queue_handler.setLevel(logging.DEBUG)

    logger = logging.getLogger()
    logger.addHandler(queue_handler)
    logger.setLevel(logging.DEBUG)
    # These loggers generates too much DEBUG noise, drowning out the important things, so force
    # the INFO level for it until https://github.com/ethereum/py-evm/issues/806 is fixed.
    logging.getLogger('p2p.peer.Peer').setLevel(logging.INFO)
    logging.getLogger('p2p.kademlia').setLevel(logging.INFO)
    logging.getLogger('p2p.discovery').setLevel(logging.INFO)
    logger.debug('Logging initialized: PID=%s', os.getpid())


def with_queued_logging(fn: Callable) -> Callable:
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        try:
            log_queue = kwargs['log_queue']
        except KeyError:
            raise KeyError("The `log_queue` argument is required when calling `{0}`".format(
                fn.__name__,
            ))
        else:
            log_level = kwargs.get('log_level', logging.INFO)
            setup_queue_logging(log_queue, level=log_level)

            inner_kwargs = dissoc(kwargs, 'log_queue', 'log_level')

            return fn(*args, **inner_kwargs)
    return inner
