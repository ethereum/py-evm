import functools
import logging
from logging import handlers
import sys

from cytoolz import dissoc


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


def setup_queue_logging(log_queue, level):
    queue_handler = handlers.QueueHandler(log_queue)
    logging.basicConfig(
        level=level,
        handlers=[queue_handler],
    )

    logger = logging.getLogger()
    logger.debug('Logging initialized')


def with_queued_logging(fn):
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        print(args, kwargs)
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
