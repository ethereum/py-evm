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
from pathlib import Path
import sys
from typing import (
    Any,
    cast,
    Dict,
    Tuple,
    TYPE_CHECKING,
    Callable,
)

from eth_utils.toolz import dissoc

from eth.tools.logging import (
    ExtendedDebugLogger,
)

from trinity._utils.shellart import (
    bold_red,
    bold_yellow,
)

if TYPE_CHECKING:
    from multiprocessing import Queue  # noqa: F401

LOG_BACKUP_COUNT = 10
LOG_MAX_MB = 5


class TrinityLogFormatter(logging.Formatter):

    def __init__(self, fmt: str, datefmt: str) -> None:
        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        record.shortname = record.name.split('.')[-1]  # type: ignore

        if record.levelno >= logging.ERROR:
            return bold_red(super().format(record))
        elif record.levelno >= logging.WARNING:
            return bold_yellow(super().format(record))
        else:
            return super().format(record)


class HasExtendedDebugLogger:
    _logger: ExtendedDebugLogger = None

    @property
    def logger(self) -> ExtendedDebugLogger:
        if self._logger is None:
            self._logger = cast(
                ExtendedDebugLogger,
                logging.getLogger(self.__module__ + '.' + self.__class__.__name__)
            )
        return self._logger


def setup_log_levels(log_levels: Dict[str, int]) -> None:
    for name, level in log_levels.items():
        logger = logging.getLogger(name)
        logger.setLevel(level)


def setup_trinity_stderr_logging(level: int=None,
                                 ) -> Tuple[Logger, Formatter, StreamHandler]:
    if level is None:
        level = logging.INFO
    logger = logging.getLogger('trinity')
    logger.setLevel(logging.DEBUG)

    handler_stream = logging.StreamHandler(sys.stderr)
    handler_stream.setLevel(level)

    # TODO: allow configuring `detailed` logging
    formatter = TrinityLogFormatter(
        fmt='%(levelname)8s  %(asctime)s  %(shortname)20s  %(message)s',
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
        logfile_path: Path,
        level: int=None) -> Tuple[Logger, 'Queue[str]', QueueListener]:
    from .mp import ctx

    if level is None:
        level = logging.DEBUG

    log_queue = ctx.Queue()

    handler_file = RotatingFileHandler(
        str(logfile_path),
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

    logger = cast(ExtendedDebugLogger, logging.getLogger())
    logger.addHandler(queue_handler)
    logger.setLevel(level)

    logger.debug('Logging initialized: PID=%s', os.getpid())


def with_queued_logging(fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    def inner(*args: Any, **kwargs: Any) -> Any:
        try:
            log_queue = kwargs['log_queue']
        except KeyError:
            raise KeyError(f"The `log_queue` argument is required when calling `{fn.__name__}`")
        else:
            level = kwargs.get('log_level', logging.INFO)
            levels = kwargs.get('log_levels', {})
            setup_queue_logging(log_queue, level)
            setup_log_levels(levels)
            inner_kwargs = dissoc(kwargs, 'log_queue', 'log_level', 'log_levels')

            return fn(*args, **inner_kwargs)
    return inner


def _set_environ_if_missing(name: str, val: str) -> None:
    """
    Set the environment variable so that other processes get the changed value.
    """
    if os.environ.get(name, '') == '':
        os.environ[name] = val


def enable_warnings_by_default() -> None:
    """
    This turns on some python and asyncio warnings, unless
    the related environment variables are already set.
    """
    _set_environ_if_missing('PYTHONWARNINGS', 'default')
    # PYTHONASYNCIODEBUG is not turned on by default because it slows down sync a *lot*
    logging.getLogger('asyncio').setLevel(logging.DEBUG)
