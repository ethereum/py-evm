from abc import ABC, abstractmethod
from typing import (
    Any,
    AsyncIterator,
    AsyncContextManager,
    Callable,
    Dict,
    Generic,
    Iterable,
    Optional,
    Tuple,
    Type,
    TYPE_CHECKING,
)


from p2p.abc import (
    AsyncioServiceAPI,
    ConnectionAPI,
    ProtocolAPI,
)
from p2p.stats.ema import EMA
from p2p.stats.percentile import Percentile
from p2p.stats.stddev import StandardDeviation

from .typing import (
    TResult,
    TRequestCommand,
    TResponseCommand,
)

if TYPE_CHECKING:
    import asyncio  # noqa: F401


class NormalizerAPI(ABC, Generic[TResponseCommand, TResult]):
    # This variable indicates how slow normalization is. If normalization requires
    # any non-trivial computation, consider it slow. Then, the Manager will run it in
    # a thread to ensure it doesn't block the main loop.
    is_normalization_slow: bool

    @staticmethod
    @abstractmethod
    def normalize_result(message: TResponseCommand) -> TResult:
        """
        Convert underlying peer message to final result
        """
        ...


class ValidatorAPI(ABC, Generic[TResult]):
    @abstractmethod
    def validate_result(self, result: TResult) -> None:
        ...


class PerformanceAPI(ABC):
    total_msgs: int
    total_items: int
    total_timeouts: int
    total_response_time: float

    response_quality_ema: EMA
    round_trip_ema: EMA
    round_trip_99th: Percentile
    round_trip_stddev: StandardDeviation
    items_per_second_ema: EMA

    @abstractmethod
    def get_stats(self) -> str:
        """
        Return a human readable string representing the stats for this tracker.
        """
        ...


class PerformanceTrackerAPI(PerformanceAPI, Generic[TRequestCommand, TResult]):
    """
    The statistics of how a command is performing.
    """

    @abstractmethod
    def record_timeout(self, timeout: float) -> None:
        ...

    @abstractmethod
    def record_response(self,
                        elapsed: float,
                        request: TRequestCommand,
                        result: TResult) -> None:
        ...


class ResponseCandidateStreamAPI(AsyncioServiceAPI, Generic[TRequestCommand, TResponseCommand]):
    response_timeout: float

    pending_request: Optional[Tuple[float, 'asyncio.Future[TResponseCommand]']]

    request_protocol_type: Type[ProtocolAPI]
    response_cmd_type: Type[TResponseCommand]

    last_response_time: float

    @abstractmethod
    def __init__(
            self,
            connection: ConnectionAPI,
            request_protocol_type: Type[ProtocolAPI],
            response_cmd_type: Type[TResponseCommand]) -> None:
        ...

    @abstractmethod
    def payload_candidates(
            self,
            request: TRequestCommand,
            tracker: PerformanceTrackerAPI[TRequestCommand, Any],
            *,
            timeout: float = None) -> AsyncIterator[TResponseCommand]:
        """
        Make a request and iterate through candidates for a valid response.

        To mark a response as valid, use `complete_request`. After that call, payload
        candidates will stop arriving.
        """
        ...

    @property
    @abstractmethod
    def response_cmd_name(self) -> str:
        ...

    @abstractmethod
    def complete_request(self) -> None:
        ...

    @property
    @abstractmethod
    def is_pending(self) -> bool:
        ...

    @abstractmethod
    def __del__(self) -> None:
        ...


class ExchangeManagerAPI(ABC, Generic[TRequestCommand, TResponseCommand, TResult]):
    _response_stream: Optional[ResponseCandidateStreamAPI[TRequestCommand, TResponseCommand]]

    tracker: PerformanceTrackerAPI[Any, TResult]

    @abstractmethod
    def __init__(
            self,
            connection: ConnectionAPI,
            requesting_on: Type[ProtocolAPI],
            listening_for: Type[TResponseCommand]) -> None:
        ...

    @abstractmethod
    async def get_result(
            self,
            request: TRequestCommand,
            normalizer: NormalizerAPI[TResponseCommand, TResult],
            validate_result: Callable[[TResult], None],
            payload_validator: Callable[[TResponseCommand], None],
            tracker: PerformanceTrackerAPI[TRequestCommand, TResult],
            timeout: float = None) -> TResult:
        ...

    @property
    @abstractmethod
    def service(self) -> ResponseCandidateStreamAPI[TRequestCommand, TResponseCommand]:
        """
        This service that needs to be running for calls to execute properly
        """
        ...

    @property
    @abstractmethod
    def is_requesting(self) -> bool:
        ...


class ExchangeAPI(ABC, Generic[TRequestCommand, TResponseCommand, TResult]):
    """
    The exchange object handles a few things, in rough order:

     - convert from friendly input arguments to the protocol arguments
     - generate the appropriate BaseRequest object
     - identify the BaseNormalizer that can convert the response payload to the desired result
     - prepare the ValidatorAPI that can validate the final result against the requested data
     - (if necessary) prepare a response payload validator, which validates data that is *not*
        present in the final result
     - issue the request to the ExchangeManager, with the request, normalizer, and validators
     - await the normalized & validated response, and return it

    TRequestCommand is the data as passed directly to the p2p command
    TResponseCommand is the data as received directly from the p2p command response
    TResult is the response data after normalization
    """
    tracker_class: Type[PerformanceTrackerAPI[Any, TResult]]
    tracker: PerformanceTrackerAPI[TRequestCommand, TResult]

    @abstractmethod
    def __init__(self, mgr: ExchangeManagerAPI[TRequestCommand, TResponseCommand, TResult]) -> None:
        ...

    @abstractmethod
    def run_exchange(self, connection: ConnectionAPI) -> AsyncContextManager[None]:
        ...

    @abstractmethod
    async def get_result(
            self,
            request: TRequestCommand,
            normalizer: NormalizerAPI[TResponseCommand, TResult],
            result_validator: ValidatorAPI[TResult],
            payload_validator: Callable[[TRequestCommand, TResponseCommand], None],
            timeout: float = None) -> TResult:
        ...

    @classmethod
    @abstractmethod
    def get_response_cmd_type(cls) -> Type[TResponseCommand]:
        ...

    @classmethod
    @abstractmethod
    def get_request_cmd_type(cls) -> Type[TRequestCommand]:
        ...

    @abstractmethod
    async def __call__(self, *args: Any, **kwargs: Any) -> None:
        ...

    @property
    @abstractmethod
    def is_requesting(self) -> bool:
        ...


class HandlerAPI(Iterable[ExchangeAPI[Any, Any, Any]]):
    _exchange_config: Dict[str, Type[ExchangeAPI[Any, Any, Any]]]

    @abstractmethod
    def __init__(self, connection: ConnectionAPI) -> None:
        ...

    @abstractmethod
    def get_stats(self) -> Dict[str, str]:
        ...
