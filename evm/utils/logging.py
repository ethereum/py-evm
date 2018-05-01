import logging
from logging import Logger
from typing import Any

TRACE_LEVEL_NUM = 5


class TraceLogger(Logger):

    def init(self, name: str, level: int) -> None:
        Logger.__init__(self, name, level)

    def trace(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.log(TRACE_LEVEL_NUM, message, *args, **kwargs)


def setup_trace_logging() -> None:
    logging.setLoggerClass(TraceLogger)
    logging.addLevelName(TRACE_LEVEL_NUM, 'TRACE')
