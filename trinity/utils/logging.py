import functools
import logging
from logging import (
    Logger,
    Formatter,
    StreamHandler
)
from logging.handlers import (
    QueueListener,
    QueueHandler,
    RotatingFileHandler,
)

import os
import sys
from typing import (
    Any,
    cast,
    Dict,
    Tuple,
    TYPE_CHECKING,
    Callable,
    Union,
)

from cytoolz import dissoc

from eth.tools.logging import (
    TraceLogger,
)

from trinity.config import (
    ChainConfig,
)

if TYPE_CHECKING:
    from multiprocessing import Queue  # noqa: F401

LOG_BACKUP_COUNT = 10
LOG_MAX_MB = 5


class HasTraceLogger:
    _logger: TraceLogger = None

    @property
    def logger(self) -> TraceLogger:
        if self._logger is None:
            self._logger = cast(
                TraceLogger,
                logging.getLogger(self.__module__ + '.' + self.__class__.__name__)
            )
        return self._logger


def setup_log_levels(log_levels: Dict[Union[None, str], int]) -> None:
    for name, level in log_levels.items():
        logger = logging.getLogger(name)
        logger.setLevel(level)


def setup_trinity_stderr_logging(level: int=logging.INFO,
                                 ) -> Tuple[Logger, Formatter, StreamHandler]:
    logger = logging.getLogger('trinity')
    logger.setLevel(logging.DEBUG)

    handler_stream = logging.StreamHandler(sys.stderr)
    handler_stream.setLevel(level)

    # TODO: allow configuring `detailed` logging
    formatter = logging.Formatter(
        fmt='%(levelname)8s  %(asctime)s  %(module)10s  %(message)s',
        datefmt='%m-%d %H:%M:%S'
    )

    handler_stream.setFormatter(formatter)

    logger.addHandler(handler_stream)

    logger.debug('Logging initialized: PID=%s', os.getpid())

    return logger, formatter, handler_stream


def setup_trinity_file_and_queue_logging(
        logger: Logger,
        formatter: Formatter,
        handler_stream: StreamHandler,
        chain_config: ChainConfig,
        level: int=logging.DEBUG) -> Tuple[Logger, 'Queue[str]', QueueListener]:
    from .mp import ctx

    log_queue = ctx.Queue()

    handler_file = RotatingFileHandler(
        str(chain_config.logfile_path),
        maxBytes=(10000000 * LOG_MAX_MB),
        backupCount=LOG_BACKUP_COUNT
    )

    handler_file.setLevel(level)
    handler_file.setFormatter(formatter)

    logger.addHandler(handler_file)

    listener = QueueListener(
        log_queue,
        handler_stream,
        handler_file,
        respect_handler_level=True,
    )

    return logger, log_queue, listener


def setup_queue_logging(log_queue: 'Queue[str]', level: int) -> None:
    queue_handler = QueueHandler(log_queue)
    queue_handler.setLevel(level)

    logger = cast(TraceLogger, logging.getLogger())
    logger.addHandler(queue_handler)
    logger.setLevel(level)

    # These loggers generates too much DEBUG noise, drowning out the important things, so force
    # the INFO level for it until https://github.com/ethereum/py-evm/issues/806 is fixed.
    logging.getLogger('p2p.kademlia').setLevel(logging.INFO)
    logging.getLogger('p2p.discovery').setLevel(logging.INFO)
    logger.debug('Logging initialized: PID=%s', os.getpid())


def with_queued_logging(fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    def inner(*args: Any, **kwargs: Any) -> Any:
        try:
            log_queue = kwargs['log_queue']
        except KeyError:
            raise KeyError("The `log_queue` argument is required when calling `{0}`".format(
                fn.__name__,
            ))
        else:
            level = kwargs.get('log_level', logging.INFO)
            setup_queue_logging(log_queue, level)

            inner_kwargs = dissoc(kwargs, 'log_queue', 'log_level')

            return fn(*args, **inner_kwargs)
    return inner
