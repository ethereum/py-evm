from abc import ABC, abstractmethod
import logging
from typing import (
    Any,
    cast,
    Generic,
    Optional,
    TypeVar,
    Union,
)

from eth_utils import ValidationError

from eth.tools.logging import TraceLogger

from p2p.protocol import (
    BaseRequest,
)
from .types import (
    TResult,
)


TRequest = TypeVar('TRequest', bound=BaseRequest[Any])


class EMA:
    """
    Represents an exponential moving average.
    https://en.wikipedia.org/wiki/Moving_average#Exponential_moving_average

    Smoothing factor, or "alpha" of the exponential moving average.

    - Closer to 0 gives you smoother, slower-to-update, data
    - Closer to 1 gives you choppier, quicker-to-update, data

    .. note::

        A smoothing factor of 1 would completely ignore history whereas 0 would
        completely ignore new data


    The initial value is the starting value for the EMA
    """
    def __init__(self, initial_value: float, smoothing_factor: float) -> None:
        self._value = initial_value
        if 0 < smoothing_factor < 1:
            self._alpha = smoothing_factor
        else:
            raise ValidationError("Smoothing factor of EMA must be between 0 and 1")

    def update(self, scalar: Union[int, float]) -> None:
        self._value = (self._value * (1 - self._alpha)) + (scalar * self._alpha)

    @property
    def value(self) -> float:
        return self._value


class BasePerformanceTracker(ABC, Generic[TRequest, TResult]):
    def __init__(self) -> None:
        self.total_msgs = 0
        self.total_items = 0
        self.total_missing = 0
        self.total_timeouts = 0
        self.total_response_time = 0.0

        # a percentage between 0-100 for how much of the requested
        # data the peer typically returns with 100 meaning they consistently
        # return all of the data we request and 0 meaning they do not return
        # only empty responses.
        self.response_quality_ema = EMA(initial_value=50, smoothing_factor=0.05)

        # an EMA of the round trip request/response time
        self.round_trip_time_ema = EMA(initial_value=1, smoothing_factor=0.05)

        # an EMA of the items per second
        self.items_per_second_ema = EMA(initial_value=1, smoothing_factor=0.05)

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
            items_per_second = 0.0
        else:
            items_per_second = self.total_response_time / self.total_items

        # msgs: total number of messages
        # items: total number of items
        # rtt: round-trip-time (avg/ema)
        # ips: items-per-second (avg/ema)
        # timeouts: total number of timeouts
        # missing: total number of missing response items
        # quality: 0-100 for how complete responses are
        return (
            'msgs=%d  items=%d  rtt=%.2f/%.2f  ips=%.5f/%.5f  '
            'timeouts=%d  missing=%d  quality=%d'
        ) % (
            self.total_msgs,
            self.total_items,
            avg_rtt,
            self.round_trip_time_ema.value,
            items_per_second,
            self.items_per_second_ema.value,
            self.total_timeouts,
            self.total_missing,
            int(self.response_quality_ema.value),
        )

    def record_timeout(self) -> None:
        self.total_msgs += 1
        self.total_timeouts += 1
        self.response_quality_ema.update(0)

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
            if request_size == 0:
                self.logger.warning(
                    "%s encountered request for zero items. This should never happen",
                    type(self).__name__,
                )
                self.response_quality_ema.update(100)
            elif response_size == 0:
                self.response_quality_ema.update(0)
            else:
                percent_returned = 100 * response_size / request_size
                self.response_quality_ema.update(percent_returned)

        self.total_items += num_items
        self.total_response_time += time
        self.round_trip_time_ema.update(time)

        if time > 0:
            throughput = num_items / time
            self.items_per_second_ema.update(throughput)
        else:
            self.logger.warning(
                "%s encountered response time of zero.  This should never happen",
                type(self).__name__,
            )
