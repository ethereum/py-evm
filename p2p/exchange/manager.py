from typing import (
    Callable,
    Type,
    TypeVar,
)

from eth_utils import (
    ValidationError,
)

from p2p.abc import (
    CommandAPI,
    ConnectionAPI,
    ProtocolAPI,
    RequestAPI,
)
from p2p.exceptions import PeerConnectionLost
from p2p.typing import TRequestPayload, TResponsePayload

from .abc import (
    ExchangeManagerAPI,
    NormalizerAPI,
    PerformanceTrackerAPI,
    ResponseCandidateStreamAPI,
)
from .candidate_stream import ResponseCandidateStream


TResult = TypeVar('TResult')


class ExchangeManager(ExchangeManagerAPI[TRequestPayload, TResponsePayload, TResult]):
    _response_stream: ResponseCandidateStreamAPI[TRequestPayload, TResponsePayload] = None

    def __init__(
            self,
            connection: ConnectionAPI,
            requesting_on: Type[ProtocolAPI],
            listening_for: Type[CommandAPI]) -> None:
        self._connection = connection
        self._request_protocol_type = requesting_on
        self._response_command_type = listening_for

    async def launch_service(self) -> None:
        if self._connection.cancel_token.triggered:
            raise PeerConnectionLost(
                f"Peer {self._connection} is gone. Ignoring new requests to it"
            )

        self._response_stream = ResponseCandidateStream(
            self._connection,
            self._request_protocol_type,
            self._response_command_type,
        )
        self._connection.run_daemon(self._response_stream)
        await self._connection.wait(self._response_stream.events.started.wait())

    @property
    def is_operational(self) -> bool:
        return self.service is not None and self.service.is_operational

    async def get_result(
            self,
            request: RequestAPI[TRequestPayload],
            normalizer: NormalizerAPI[TResponsePayload, TResult],
            validate_result: Callable[[TResult], None],
            payload_validator: Callable[[TResponsePayload], None],
            tracker: PerformanceTrackerAPI[RequestAPI[TRequestPayload], TResult],
            timeout: float = None) -> TResult:

        if not self.is_operational:
            if self.service is None or not self.service.is_cancelled:
                raise ValidationError(
                    f"Must call `launch_service` before sending request to {self._connection}"
                )
            else:
                raise PeerConnectionLost(
                    f"Response stream closed before sending request to {self._connection}"
                )

        stream = self._response_stream

        async for payload in stream.payload_candidates(request, tracker, timeout=timeout):
            try:
                payload_validator(payload)

                if normalizer.is_normalization_slow:
                    # We don't expose the `_run_in_executor` API as part of the formal service ABC
                    result = await stream._run_in_executor(  # type: ignore
                        None,
                        normalizer.normalize_result,
                        payload
                    )
                else:
                    result = normalizer.normalize_result(payload)

                validate_result(result)
            except ValidationError as err:
                self.service.logger.debug(
                    "Response validation failed for pending %s request from connection %s: %s",
                    stream.response_cmd_name,
                    self._connection,
                    err,
                )
                # If this response was just for the wrong request, we'll catch the right one later.
                # Otherwise, this request will eventually time out.
                continue
            else:
                tracker.record_response(
                    stream.last_response_time,
                    request,
                    result,
                )
                stream.complete_request()
                return result

        raise PeerConnectionLost(f"Response stream of {self._connection} was apparently closed")

    @property
    def service(self) -> ResponseCandidateStreamAPI[TRequestPayload, TResponsePayload]:
        """
        This service that needs to be running for calls to execute properly
        """
        return self._response_stream

    @property
    def is_requesting(self) -> bool:
        return self._response_stream is not None and self._response_stream.is_pending
