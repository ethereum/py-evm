import copy
import logging
from logging import (
    StreamHandler
)
from logging.handlers import (
    RotatingFileHandler,
)
import os
from pathlib import Path
import pickle
import socket
import sys
from typing import (
    Dict,
    Type,
    TypeVar,
)

from trinity._utils.shellart import (
    bold_red,
    bold_yellow,
)
from trinity._utils.socket import BufferedSocket, IPCSocketServer
from trinity._utils.ipc import wait_for_ipc
from trinity.boot_info import BootInfo

LOG_BACKUP_COUNT = 10
LOG_MAX_MB = 5


THandler = TypeVar("THandler", bound="IPCHandler")


class IPCHandler(logging.Handler):
    logger = logging.getLogger('trinity._utils.logging.IPCHandler')

    def __init__(self, sock: socket.socket):
        self._socket = BufferedSocket(sock)
        super().__init__()

    @classmethod
    def connect(cls: Type[THandler], path: Path) -> THandler:
        wait_for_ipc(path)
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        cls.logger.debug("Opened connection to %s: %s", path, s)
        s.connect(str(path))
        return cls(s)

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        msg = self.format(record)
        new_record = copy.copy(record)
        new_record.message = msg
        new_record.msg = msg
        new_record.args = None
        new_record.exc_info = None
        new_record.exc_text = None
        return new_record

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg_data = pickle.dumps(self.prepare(record))
            msg_length_data = len(msg_data).to_bytes(4, 'big')
            self._socket.sendall(msg_length_data + msg_data)
        except Exception:
            self.handleError(record)


class IPCListener(IPCSocketServer):
    logger = logging.getLogger('trinity._utils.logging.IPCListener')

    def __init__(self, *handlers: logging.Handler) -> None:
        super().__init__()
        self.handlers = handlers

    def serve_conn(self, sock: BufferedSocket) -> None:
        while self.is_running:
            try:
                length_data = sock.read_exactly(4)
            except OSError as err:
                self.logger.debug("%s: closing client connection: %s", self, err)
                break
            except Exception:
                self.logger.exception("Error reading serialized record length data")
                break

            data_length = int.from_bytes(length_data, 'big')

            try:
                record_bytes = sock.read_exactly(data_length)
            except OSError as err:
                self.logger.debug("%s: closing client connection: %s", self, err)
                break
            except Exception:
                self.logger.exception("Error reading serialized log record data")
                break

            record = pickle.loads(record_bytes)

            for handler in self.handlers:
                if record.levelno >= handler.level:
                    handler.handle(record)


class TrinityLogFormatter(logging.Formatter):

    def __init__(self, fmt: str) -> None:
        super().__init__(fmt)

    def format(self, record: logging.LogRecord) -> str:
        record.shortname = record.name.split('.')[-1]  # type: ignore

        if record.levelno >= logging.ERROR:
            return bold_red(super().format(record))
        elif record.levelno >= logging.WARNING:
            return bold_yellow(super().format(record))
        else:
            return super().format(record)


LOG_FORMATTER = TrinityLogFormatter(
    fmt='%(levelname)8s  %(asctime)s  %(shortname)20s  %(message)s',
)


def set_logger_levels(log_levels: Dict[str, int],
                      *handlers: logging.Handler) -> None:
    for name, level in log_levels.items():

        # The root logger is configured separately
        if name is None:
            continue

        logger = logging.getLogger(name)
        logger.propagate = False
        logger.setLevel(level)

        for handler in handlers:
            handler.setLevel(level)
            handler.setFormatter(LOG_FORMATTER)


def setup_stderr_logging(level: int = None) -> StreamHandler:
    if level is None:
        level = logging.INFO
    logger = logging.getLogger()

    handler_stream = logging.StreamHandler(sys.stderr)

    if level is not None:
        handler_stream.setLevel(level)
    handler_stream.setFormatter(LOG_FORMATTER)

    logger.addHandler(handler_stream)

    logger.debug('Logging initialized for stderr: PID=%s', os.getpid())

    return handler_stream


def setup_file_logging(
        logfile_path: Path,
        level: int = None) -> RotatingFileHandler:
    if level is None:
        level = logging.DEBUG
    logger = logging.getLogger()

    handler_file = RotatingFileHandler(
        str(logfile_path),
        maxBytes=(10000000 * LOG_MAX_MB),
        backupCount=LOG_BACKUP_COUNT,
        delay=True
    )
    if logfile_path.exists():
        handler_file.doRollover()

    if level is not None:
        handler_file.setLevel(level)
    handler_file.setFormatter(LOG_FORMATTER)

    logger.addHandler(handler_file)

    return handler_file


def setup_child_process_logging(boot_info: BootInfo) -> None:
    # We get the root logger here to ensure that all logs are given a chance to
    # pass through this handler
    logger = logging.getLogger()
    logger.setLevel(boot_info.child_process_log_level)

    set_logger_levels(boot_info.logger_levels)

    ipc_handler = IPCHandler.connect(boot_info.trinity_config.logging_ipc_path)
    ipc_handler.setLevel(boot_info.child_process_log_level)

    logger.addHandler(ipc_handler)

    logger.debug(
        'Logging initialized for file %s: PID=%s',
        boot_info.trinity_config.logging_ipc_path.resolve(),
        os.getpid(),
    )


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
