from abc import ABC, abstractmethod
from typing import (
    Any,
    Generic,
    Optional,
    TypeVar,
    Union,
)

from eth_utils import ValidationError

from p2p.protocol import (
    BaseRequest,
)

from trinity.utils.logging import HasTraceLogger
from .constants import ROUND_TRIP_TIMEOUT
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


class BasePerformanceTracker(ABC, HasTraceLogger, Generic[TRequest, TResult]):
    def __init__(self) -> None:
        self.total_msgs = 0
        self.total_items = 0
        self.total_timeouts = 0
        self.total_response_time = 0.0

        # a percentage between 0-100 for how much of the requested
        # data the peer typically returns with 100 meaning they consistently
        # return all of the data we request and 0 meaning they only return
        # empty responses.
        self.response_quality_ema = EMA(initial_value=0, smoothing_factor=0.05)

        # an EMA of the round trip request/response time
        self.round_trip_ema = EMA(initial_value=ROUND_TRIP_TIMEOUT, smoothing_factor=0.05)

        # an EMA of the items per second
        self.items_per_second_ema = EMA(initial_value=0, smoothing_factor=0.05)

    @abstractmethod
    def _get_request_size(self, request: TRequest) -> Optional[int]:
        """
        The request size represents the number of *things* that were requested,
        not taking into account the sizes of individual items.

        Some requests cannot be used to determine the expected size.  In this
        case `None` should be returned.  (Specifically the `GetBlockHeaders`
        anchored to a block hash.
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
        if not self.total_response_time:
            items_per_second = 0.0
        else:
            items_per_second = self.total_items / self.total_response_time

        # msgs: total number of messages
        # items: total number of items
        # rtt: round-trip-time (avg/ema)
        # ips: items-per-second (avg/ema)
        # timeouts: total number of timeouts
        # missing: total number of missing response items
        # quality: 0-100 for how complete responses are
        return (
            'msgs=%d  items=%d  rtt=%.2f/%.2f  ips=%.5f/%.5f  '
            'timeouts=%d  quality=%d'
        ) % (
            self.total_msgs,
            self.total_items,
            avg_rtt,
            self.round_trip_ema.value,
            items_per_second,
            self.items_per_second_ema.value,
            self.total_timeouts,
            int(self.response_quality_ema.value),
        )

    def record_timeout(self, timeout: float) -> None:
        self.total_msgs += 1
        self.total_timeouts += 1
        self.response_quality_ema.update(0)
        self.items_per_second_ema.update(0)
        self.round_trip_ema.update(timeout)

    def record_response(self,
                        elapsed: float,
                        request: TRequest,
                        result: TResult) -> None:
        self.total_msgs += 1

        request_size = self._get_request_size(request)
        response_size = self._get_result_size(result)
        num_items = self._get_result_item_count(result)

        if request_size is None:
            # In the event that request size cannot be determined we skip stats
            # tracking based on request size.
            pass

        elif response_size > request_size:
            self.logger.warning(
                "%s got oversized response.  requested: %d  received: %d",
                type(self).__name__,
                request_size,
                response_size,
            )
        else:
            if request_size == 0:
                self.logger.warning(
                    "%s encountered request for zero items. This should never happen",
                    type(self).__name__,
                )
                # we intentionally don't update the ema here since this is an
                # odd and unexpected case.
            elif response_size == 0:
                self.response_quality_ema.update(0)
            else:
                percent_returned = 100 * response_size / request_size
                self.response_quality_ema.update(percent_returned)

        self.total_items += num_items
        self.total_response_time += elapsed
        self.round_trip_ema.update(elapsed)

        if elapsed > 0:
            throughput = num_items / elapsed
            self.items_per_second_ema.update(throughput)
        else:
            self.logger.warning(
                "%s encountered response time of zero.  This should never happen",
                type(self).__name__,
            )
