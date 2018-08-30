from abc import ABC, abstractmethod
import logging
from typing import (
    Any,
    cast,
    Generic,
    Optional,
    TypeVar,
)

from eth.tools.logging import TraceLogger

from p2p.protocol import (
    BaseRequest,
)
from .types import (
    TResult,
)


TRequest = TypeVar('TRequest', bound=BaseRequest[Any])


class BasePerformanceTracker(ABC, Generic[TRequest, TResult]):
    def __init__(self) -> None:
        self.total_msgs = 0
        self.total_items = 0
        self.total_missing = 0
        self.total_timeouts = 0
        self.total_response_time = 0.0

    _logger: TraceLogger = None

    @property
    def logger(self) -> TraceLogger:
        if self._logger is None:
            self._logger = cast(
                TraceLogger,
                logging.getLogger(self.__module__ + '.' + self.__class__.__name__)
            )
        return self._logger

    @abstractmethod
    def _get_request_size(self, request: TRequest) -> Optional[int]:
        """
        The request size represents the number of *things* that were requested,
        not taking into account the sizes of individual items.
        """
        pass

    @abstractmethod
    def _get_result_size(self, result: TResult) -> int:
        """
        The result size represents the number of *things* that were returned,
        not taking into account the sizes of individual items.
        """
        pass

    @abstractmethod
    def _get_result_item_count(self, result: TResult) -> int:
        """
        The item count is intended to more accurately represent the size of the
        response, taking into account things like the size of individual
        response items such as the number of transactions in a block.
        """
        pass

    def get_stats(self) -> str:
        """
        Return a human readable string representing the stats for this tracker.
        """
        if not self.total_msgs:
            return 'None'
        avg_rtt = self.total_response_time / self.total_msgs
        if not self.total_items:
            per_item_rtt = 0.0
        else:
            per_item_rtt = self.total_response_time / self.total_items
        return 'count=%d  items=%d  avg_rtt=%.2f  avg_tpi=%.5f  timeouts=%d  missing=%d' % (
            self.total_msgs,
            self.total_items,
            avg_rtt,
            per_item_rtt,
            self.total_timeouts,
            self.total_missing
        )

    def record_timeout(self) -> None:
        self.total_msgs += 1
        self.total_timeouts += 1

    def record_response(self,
                        time: float,
                        request: TRequest,
                        result: TResult) -> None:
        self.total_msgs += 1

        request_size = self._get_request_size(request)
        response_size = self._get_result_size(result)
        num_items = self._get_result_item_count(result)

        if request_size is None:
            pass
        elif response_size > request_size:
            self.logger.warning(
                "%s got oversized response.  requested: %d  received: %d",
                type(self).__name__,
                request_size,
                response_size,
            )
        else:
            self.total_missing += (request_size - response_size)

        self.total_items += num_items
        self.total_response_time += time
