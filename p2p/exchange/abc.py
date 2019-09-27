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
    CommandAPI,
    ConnectionAPI,
    RequestAPI,
    ProtocolAPI,
)
from p2p.stats.ema import EMA
from p2p.stats.percentile import Percentile
from p2p.stats.stddev import StandardDeviation
from p2p.typing import (
    TRequestPayload,
    TResponsePayload,
)

from .typing import TResult, TRequest, TResponse

if TYPE_CHECKING:
    import asyncio  # noqa: F401


class NormalizerAPI(ABC, Generic[TResponsePayload, TResult]):
    # This variable indicates how slow normalization is. If normalization requires
    # any non-trivial computation, consider it slow. Then, the Manager will run it in
    # a thread to ensure it doesn't block the main loop.
    is_normalization_slow: bool

    @staticmethod
    @abstractmethod
    def normalize_result(message: TResponsePayload) -> TResult:
        """
        Convert underlying peer message to final result
        """
        ...


class ValidatorAPI(ABC, Generic[TResponse]):
    @abstractmethod
    def validate_result(self, result: TResponse) -> None:
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


class PerformanceTrackerAPI(PerformanceAPI, Generic[TRequest, TResult]):
    """
    The statistics of how a command is performing.
    """

    @abstractmethod
    def record_timeout(self, timeout: float) -> None:
        ...

    @abstractmethod
    def record_response(self,
                        elapsed: float,
                        request: TRequest,
                        result: TResult) -> None:
        ...


class ResponseCandidateStreamAPI(AsyncioServiceAPI, Generic[TRequestPayload, TResponsePayload]):
    response_timeout: float

    pending_request: Optional[Tuple[float, 'asyncio.Future[TResponsePayload]']]

    request_protocol_type: Type[ProtocolAPI]
    response_cmd_type: Type[CommandAPI]

    last_response_time: float

    @abstractmethod
    def __init__(
            self,
            connection: ConnectionAPI,
            request_protocol_type: Type[ProtocolAPI],
            response_cmd_type: Type[CommandAPI]) -> None:
        ...

    @abstractmethod
    def payload_candidates(
            self,
            request: RequestAPI[TRequestPayload],
            tracker: PerformanceTrackerAPI[RequestAPI[TRequestPayload], Any],
            *,
            timeout: float = None) -> AsyncIterator[TResponsePayload]:
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


class ExchangeManagerAPI(ABC, Generic[TRequestPayload, TResponsePayload, TResult]):
    _response_stream: Optional[ResponseCandidateStreamAPI[TRequestPayload, TResponsePayload]]

    tracker: PerformanceTrackerAPI[Any, TResult]

    @abstractmethod
    def __init__(
            self,
            connection: ConnectionAPI,
            requesting_on: Type[ProtocolAPI],
            listening_for: Type[CommandAPI]) -> None:
        ...

    @abstractmethod
    async def get_result(
            self,
            request: RequestAPI[TRequestPayload],
            normalizer: NormalizerAPI[TResponsePayload, TResult],
            validate_result: Callable[[TResult], None],
            payload_validator: Callable[[TResponsePayload], None],
            tracker: PerformanceTrackerAPI[RequestAPI[TRequestPayload], TResult],
            timeout: float = None) -> TResult:
        ...

    @property
    @abstractmethod
    def service(self) -> ResponseCandidateStreamAPI[TRequestPayload, TResponsePayload]:
        """
        This service that needs to be running for calls to execute properly
        """
        ...

    @property
    @abstractmethod
    def is_requesting(self) -> bool:
        ...


class ExchangeAPI(Generic[TRequestPayload, TResponsePayload, TResult]):
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

    TRequestPayload is the data as passed directly to the p2p command
    TResponsePayload is the data as received directly from the p2p command response
    TResult is the response data after normalization
    """
    request_class: Type[RequestAPI[TRequestPayload]]
    tracker_class: Type[PerformanceTrackerAPI[Any, TResult]]
    tracker: PerformanceTrackerAPI[RequestAPI[TRequestPayload], TResult]

    @abstractmethod
    def run_exchange(self, connection: ConnectionAPI) -> AsyncContextManager[None]:
        ...

    @abstractmethod
    async def get_result(
            self,
            request: RequestAPI[TRequestPayload],
            normalizer: NormalizerAPI[TResponsePayload, TResult],
            result_validator: ValidatorAPI[TResult],
            payload_validator: Callable[[TRequestPayload, TResponsePayload], None],
            timeout: float = None) -> TResult:
        ...

    @classmethod
    @abstractmethod
    def get_response_cmd_type(cls) -> Type[CommandAPI]:
        ...

    @classmethod
    @abstractmethod
    def get_request_cmd_type(cls) -> Type[CommandAPI]:
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
