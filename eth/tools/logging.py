import logging
from typing import Any

from cached_property import cached_property

DEBUG2_LEVEL_NUM = 8


class ExtendedDebugLogger(logging.Logger):

    @cached_property
    def show_debug2(self) -> bool:
        return self.isEnabledFor(DEBUG2_LEVEL_NUM)

    def debug2(self, message: str, *args: Any, **kwargs: Any) -> None:
        if self.show_debug2:
            self.log(DEBUG2_LEVEL_NUM, message, *args, **kwargs)


def setup_extended_logging() -> None:
    logging.setLoggerClass(ExtendedDebugLogger)
    logging.addLevelName(DEBUG2_LEVEL_NUM, 'DEBUG2')
    setattr(logging, 'DEBUG2', DEBUG2_LEVEL_NUM)  # typing: ignore
