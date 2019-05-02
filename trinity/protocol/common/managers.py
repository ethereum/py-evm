import asyncio
import time
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Generic,
    FrozenSet,
    Tuple,
    Type,
    cast,
)

from cancel_token import CancelToken

from eth_utils import (
    ValidationError,
)

from p2p._utils import ensure_global_asyncio_executor
from p2p.constants import BLACKLIST_SECONDS_TOO_MANY_TIMEOUTS
from p2p.exceptions import PeerConnectionLost
from p2p.p2p_proto import DisconnectReason
from p2p.peer import BasePeer, PeerSubscriber
from p2p.protocol import (
    BaseRequest,
    Command,
    TRequestPayload,
)
from p2p.service import BaseService
from p2p.token_bucket import TokenBucket, NotEnoughTokens

from trinity.exceptions import AlreadyWaiting

from .constants import (
    ROUND_TRIP_TIMEOUT,
    NUM_QUEUED_REQUESTS,
    TIMEOUT_BUCKET_CAPACITY,
    TIMEOUT_BUCKET_RATE,
)
from .normalizers import BaseNormalizer
from .trackers import BasePerformanceTracker
from .types import (
    TResponsePayload,
    TResult,
)


class ResponseCandidateStream(
        PeerSubscriber,
        BaseService,
        Generic[TRequestPayload, TResponsePayload]):

    #
    # PeerSubscriber
    #
    @property
    def subscription_msg_types(self) -> FrozenSet[Type[Command]]:
        return frozenset({self.response_msg_type})

    msg_queue_maxsize = 100

    response_timeout: float = ROUND_TRIP_TIMEOUT

    pending_request: Tuple[float, 'asyncio.Future[TResponsePayload]'] = None

    _peer: BasePeer

    def __init__(
            self,
            peer: BasePeer,
            response_msg_type: Type[Command],
            token: CancelToken) -> None:
        super().__init__(token)
        self._peer = peer
        self.response_msg_type = response_msg_type
        self._lock = asyncio.Lock()

        # token bucket for limiting timeouts.
        # - Refills at 1-token every 5 minutes
        # - Max capacity of 3 tokens
        self.timeout_bucket = TokenBucket(TIMEOUT_BUCKET_RATE, TIMEOUT_BUCKET_CAPACITY)

    async def payload_candidates(
            self,
            request: BaseRequest[TRequestPayload],
            tracker: BasePerformanceTracker[BaseRequest[TRequestPayload], Any],
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
                f"or peer: {self._peer}"
            )

        start_at = time.perf_counter()

        try:
            self._request(request)
            while self._is_pending():
                timeout_remaining = max(0, total_timeout - (time.perf_counter() - start_at))

                try:
                    yield await self._get_payload(timeout_remaining)
                except TimeoutError as err:
                    tracker.record_timeout()

                    # If the peer has timeoud out too many times, desconnect
                    # and blacklist them
                    try:
                        self.timeout_bucket.take_nowait()
                    except NotEnoughTokens:
                        self.logger.warning(
                            "Blacklisting and disconnecting from %s due to too many timeouts",
                            self._peer,
                        )
                        self._peer.connection_tracker.record_blacklist(
                            self._peer.remote,
                            BLACKLIST_SECONDS_TOO_MANY_TIMEOUTS,
                            f"Too many timeouts: {err}",
                        )
                        self._peer.disconnect_nowait(DisconnectReason.timeout)
                        await self.cancellation()
                    finally:
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

        with self.subscribe_peer(self._peer):
            while self.is_operational:
                peer, cmd, msg = await self.wait(self.msg_queue.get())
                if peer != self._peer:
                    self.logger.error("Unexpected peer: %s  expected: %s", peer, self._peer)
                    continue
                elif isinstance(cmd, self.response_msg_type):
                    await self._handle_msg(cast(TResponsePayload, msg))
                else:
                    self.logger.warning("Unexpected payload type: %s", cmd.__class__.__name__)

    async def _handle_msg(self, msg: TResponsePayload) -> None:
        if self.pending_request is None:
            self.logger.debug(
                "Got unexpected %s payload from %s", self.response_msg_name, self._peer
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

    def _request(self, request: BaseRequest[TRequestPayload]) -> None:
        if not self._lock.locked():
            # This is somewhat of an invariant check but since there the
            # linkage between the lock and this method are loose this sanity
            # check seems appropriate.
            raise Exception("Invariant: cannot issue a request without an acquired lock")

        self._peer.sub_proto.send_request(request)

        future: 'asyncio.Future[TResponsePayload]' = asyncio.Future()
        self.pending_request = (time.perf_counter(), future)

    def _is_pending(self) -> bool:
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

    def deregister_peer(self, peer: BasePeer) -> None:
        if self.pending_request is not None:
            self.logger.debug("Peer stream %r shutting down, cancelling the pending request", self)
            _, future = self.pending_request
            try:
                future.set_exception(PeerConnectionLost(
                    f"Pending request can't complete: {self} peer went offline"
                ))
            except asyncio.InvalidStateError:
                self.logger.debug(
                    "%s cancelled pending future in deregister, but it was already done",
                    self,
                )

    def __repr__(self) -> str:
        return f'<ResponseCandidateStream({self._peer!s}, {self.response_msg_type!r})>'


class ExchangeManager(Generic[TRequestPayload, TResponsePayload, TResult]):
    _response_stream: ResponseCandidateStream[TRequestPayload, TResponsePayload] = None

    def __init__(
            self,
            peer: BasePeer,
            listening_for: Type[Command],
            cancel_token: CancelToken) -> None:
        self._peer = peer
        self._cancel_token = cancel_token
        self._response_command_type = listening_for

        # This TokenBucket allows for the occasional invalid response at a
        # maximum rate of 1-per-10-minutes and allowing up to two in quick
        # succession.  We *allow* invalid responses because the ETH protocol
        # doesn't have strong correlation between request/response and certain
        # networking conditions can result in us interpreting a legitimate
        # message as an invalid response if messages arrive out of order or
        # late.
        self._invalid_response_bucket = TokenBucket(1 / 600, 2)

    async def launch_service(self) -> None:
        if self._cancel_token.triggered:
            raise PeerConnectionLost("Peer %s is gone. Ignoring new requests to it" % self._peer)

        self._response_stream = ResponseCandidateStream(
            self._peer,
            self._response_command_type,
            self._cancel_token,
        )
        self._peer.run_daemon(self._response_stream)
        await self._response_stream.events.started.wait()

    @property
    def is_operational(self) -> bool:
        return self.service is not None and self.service.is_operational

    async def get_result(
            self,
            request: BaseRequest[TRequestPayload],
            normalizer: BaseNormalizer[TResponsePayload, TResult],
            validate_result: Callable[[TResult], None],
            payload_validator: Callable[[TResponsePayload], None],
            tracker: BasePerformanceTracker[BaseRequest[TRequestPayload], TResult],
            timeout: float = None) -> TResult:

        if not self.is_operational:
            if self.service is None or not self.service.is_cancelled:
                raise ValidationError(
                    f"Must call `launch_service` before sending request to {self._peer}"
                )
            else:
                raise PeerConnectionLost(
                    f"Response stream closed before sending request to {self._peer}"
                )

        stream = self._response_stream

        async for payload in stream.payload_candidates(request, tracker, timeout=timeout):
            try:
                payload_validator(payload)

                if normalizer.is_normalization_slow:
                    result = await stream._run_in_executor(
                        # We just retrieve the global executor that was created when the
                        # Node launches. The node manages the lifecycle of the executor.
                        ensure_global_asyncio_executor(),
                        normalizer.normalize_result,
                        payload
                    )
                else:
                    result = normalizer.normalize_result(payload)

                validate_result(result)
            except ValidationError as err:
                self.service.logger.debug(
                    "Response validation failed for pending %s request from peer %s: %s",
                    stream.response_msg_name,
                    self._peer,
                    err,
                )
                try:
                    self._invalid_response_bucket.take_nowait()
                except NotEnoughTokens:
                    self.service.logger.warning(
                        "Blacklisting and disconnecting from %s due to too many invalid responses",
                        self._peer,
                    )
                    self._peer.disconnect_nowait(DisconnectReason.bad_protocol)
                    await self.service.cancellation()
                    # re-raise the outer ValidationError exception
                    raise err
                else:
                    continue
            else:
                tracker.record_response(
                    stream.last_response_time,
                    request,
                    result,
                )
                stream.complete_request()
                return result

        raise ValidationError("Manager is not pending a response, but no valid response received")

    @property
    def service(self) -> BaseService:
        """
        This service that needs to be running for calls to execute properly
        """
        return self._response_stream
