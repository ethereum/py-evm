import logging
from typing import Any

DEBUG2_LEVEL_NUM = 8


class ExtendedDebugLogger(logging.Logger):

    def debug2(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.log(DEBUG2_LEVEL_NUM, message, *args, **kwargs)


def setup_extended_logging() -> None:
    logging.setLoggerClass(ExtendedDebugLogger)
    logging.addLevelName(DEBUG2_LEVEL_NUM, 'DEBUG2')
    setattr(logging, 'DEBUG2', DEBUG2_LEVEL_NUM)  # typing: ignore
