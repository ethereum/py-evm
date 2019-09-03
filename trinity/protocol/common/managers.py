import asyncio
import time
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Generic,
    Tuple,
    Type,
)

from eth_utils import (
    ValidationError,
)

from p2p.abc import (
    CommandAPI,
    ConnectionAPI,
    ProtocolAPI,
    RequestAPI,
    TRequestPayload,
)
from p2p.exceptions import (
    PeerConnectionLost,
    UnknownProtocol,
)
from p2p.service import BaseService

from trinity.exceptions import AlreadyWaiting

from .constants import (
    ROUND_TRIP_TIMEOUT,
    NUM_QUEUED_REQUESTS,
)
from .normalizers import BaseNormalizer
from .trackers import BasePerformanceTracker
from .types import (
    TResponsePayload,
    TResult,
)


class ResponseCandidateStream(
        BaseService,
        Generic[TRequestPayload, TResponsePayload]):
    response_timeout: float = ROUND_TRIP_TIMEOUT

    pending_request: Tuple[float, 'asyncio.Future[TResponsePayload]'] = None

    request_protocol_type: Type[ProtocolAPI]
    response_cmd_type: Type[CommandAPI]
    _connection: ConnectionAPI

    def __init__(
            self,
            connection: ConnectionAPI,
            request_protocol_type: Type[ProtocolAPI],
            response_msg_type: Type[CommandAPI]) -> None:
        super().__init__(connection.cancel_token)
        self._connection = connection
        self.request_protocol_type = request_protocol_type
        try:
            self.request_protocol = self._connection.get_multiplexer().get_protocol_by_type(
                request_protocol_type,
            )
        except UnknownProtocol as err:
            raise UnknownProtocol(
                f"Response candidate stream configured to use "
                f"{request_protocol_type} which is not available in the "
                f"Multiplexer"
            ) from err

        self.response_msg_type = response_msg_type
        self._lock = asyncio.Lock()

    async def payload_candidates(
            self,
            request: RequestAPI[TRequestPayload],
            tracker: BasePerformanceTracker[RequestAPI[TRequestPayload], Any],
            *,
            timeout: float = None) -> AsyncGenerator[TResponsePayload, None]:
        """
        Make a request and iterate through candidates for a valid response.

        To mark a response as valid, use `complete_request`. After that call, payload
        candidates will stop arriving.
        """
        total_timeout = self.response_timeout if timeout is None else timeout

        # The _lock ensures that we never have two concurrent requests to a
        # single peer for a single command pair in flight.
        try:
            await self.wait(self._lock.acquire(), timeout=total_timeout * NUM_QUEUED_REQUESTS)
        except TimeoutError:
            raise AlreadyWaiting(
                f"Timed out waiting for {self.response_msg_name} request lock "
                f"or connection: {self._connection}"
            )

        start_at = time.perf_counter()

        try:
            self._request(request)
            while self.is_pending:
                timeout_remaining = max(0, total_timeout - (time.perf_counter() - start_at))

                try:
                    yield await self._get_payload(timeout_remaining)
                except TimeoutError as err:
                    tracker.record_timeout(total_timeout)
                    raise
        finally:
            self._lock.release()

    @property
    def response_msg_name(self) -> str:
        return self.response_msg_type.__name__

    def complete_request(self) -> None:
        if self.pending_request is None:
            self.logger.warning("`complete_request` was called when there was no pending request")
        self.pending_request = None

    #
    # Service API
    #
    async def _run(self) -> None:
        self.logger.debug("Launching %r", self)

        # mypy doesn't recognizet the `TResponsePayload` as being an allowed
        # variant of the expected `Payload` type.
        with self._connection.add_command_handler(self.response_msg_type, self._handle_msg):  # type: ignore  # noqa: E501
            await self.cancellation()

    async def _handle_msg(self, connection: ConnectionAPI, msg: TResponsePayload) -> None:
        if self.pending_request is None:
            self.logger.debug(
                "Got unexpected %s payload from %s", self.response_msg_name, self._connection
            )
            return

        send_time, future = self.pending_request
        self.last_response_time = time.perf_counter() - send_time
        try:
            future.set_result(msg)
        except asyncio.InvalidStateError:
            self.logger.debug(
                "%s received a message response, but future was already done",
                self,
            )

    async def _get_payload(self, timeout: float) -> TResponsePayload:
        send_time, future = self.pending_request
        try:
            payload = await self.wait(future, timeout=timeout)
        finally:
            self.pending_request = None

        # payload might be invalid, so prepare for another call to _get_payload()
        self.pending_request = (send_time, asyncio.Future())

        return payload

    def _request(self, request: RequestAPI[TRequestPayload]) -> None:
        if not self._lock.locked():
            # This is somewhat of an invariant check but since there the
            # linkage between the lock and this method are loose this sanity
            # check seems appropriate.
            raise Exception("Invariant: cannot issue a request without an acquired lock")

        # TODO: better API for getting at the protocols from the connection....
        self.request_protocol.send_request(request)

        future: 'asyncio.Future[TResponsePayload]' = asyncio.Future()
        self.pending_request = (time.perf_counter(), future)

    @property
    def is_pending(self) -> bool:
        return self.pending_request is not None

    async def _cleanup(self) -> None:
        if self.pending_request is not None:
            self.logger.debug("Stream %r shutting down, cancelling the pending request", self)
            _, future = self.pending_request
            try:
                future.set_exception(PeerConnectionLost(
                    f"Pending request can't complete: {self} is shutting down"
                ))
            except asyncio.InvalidStateError:
                self.logger.debug(
                    "%s cancelled pending future in cleanup, but it was already done",
                    self,
                )

    def __del__(self) -> None:
        if self.pending_request is not None:
            _, future = self.pending_request
            if future.cancel():
                self.logger.debug("Forcefully cancelled a pending response in %s", self)

    def __repr__(self) -> str:
        return f'<ResponseCandidateStream({self._connection!s}, {self.response_msg_type!r})>'


class ExchangeManager(Generic[TRequestPayload, TResponsePayload, TResult]):
    _response_stream: ResponseCandidateStream[TRequestPayload, TResponsePayload] = None

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
            normalizer: BaseNormalizer[TResponsePayload, TResult],
            validate_result: Callable[[TResult], None],
            payload_validator: Callable[[TResponsePayload], None],
            tracker: BasePerformanceTracker[RequestAPI[TRequestPayload], TResult],
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
                    result = await stream._run_in_executor(
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
                    stream.response_msg_name,
                    self._connection,
                    err,
                )
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
    def service(self) -> BaseService:
        """
        This service that needs to be running for calls to execute properly
        """
        return self._response_stream

    @property
    def is_requesting(self) -> bool:
        return self._response_stream is not None and self._response_stream.is_pending
