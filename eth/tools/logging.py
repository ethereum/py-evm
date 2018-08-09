import logging
from typing import Any

TRACE_LEVEL_NUM = 5


class TraceLogger(logging.Logger):

    def trace(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.log(TRACE_LEVEL_NUM, message, *args, **kwargs)


def setup_trace_logging() -> None:
    logging.setLoggerClass(TraceLogger)
    logging.addLevelName(TRACE_LEVEL_NUM, 'TRACE')
    setattr(logging, 'TRACE', TRACE_LEVEL_NUM)  # typing: ignore
