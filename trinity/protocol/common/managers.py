import asyncio
import time
from typing import (  # noqa: F401 -- AsyncGenerator needed by mypy
    Any,
    AsyncGenerator,
    Callable,
    Generic,
    Set,
    Tuple,
    Type,
    cast,
)

from cancel_token import CancelToken

from eth_utils import (
    ValidationError,
)

from p2p.exceptions import PeerConnectionLost
from p2p.peer import BasePeer, PeerSubscriber
from p2p.protocol import (
    BaseRequest,
    Command,
    TRequestPayload,
)
from p2p.service import BaseService

from trinity.exceptions import AlreadyWaiting

from .normalizers import BaseNormalizer
from .types import (
    TResponsePayload,
    TResult,
)


class ResponseTimeTracker:

    def __init__(self) -> None:
        self.total_msgs = 0
        self.total_items = 0
        self.total_timeouts = 0
        self.total_response_time = 0.0

    def get_stats(self) -> str:
        if not self.total_msgs:
            return 'None'
        avg_rtt = self.total_response_time / self.total_msgs
        if not self.total_items:
            per_item_rtt = 0.0
        else:
            per_item_rtt = self.total_response_time / self.total_items
        return 'count=%d, items=%d, avg_rtt=%.2f, avg_time_per_item=%.5f, timeouts=%d' % (
            self.total_msgs, self.total_items, avg_rtt, per_item_rtt, self.total_timeouts)

    def add(self, time: float, size: int) -> None:
        self.total_msgs += 1
        self.total_items += size
        self.total_response_time += time


class ResponseCandidateStream(
        PeerSubscriber,
        BaseService,
        Generic[TRequestPayload, TResponsePayload]):

    #
    # PeerSubscriber
    #
    @property
    def subscription_msg_types(self) -> Set[Type[Command]]:
        return {self.response_msg_type}

    msg_queue_maxsize = 100

    response_timout: int = 20

    pending_request: Tuple[float, 'asyncio.Future[TResponsePayload]'] = None

    _peer: BasePeer

    def __init__(
            self,
            peer: BasePeer,
            response_msg_type: Type[Command],
            token: CancelToken) -> None:
        super().__init__(token)
        self._peer = peer
        self.response_times = ResponseTimeTracker()
        self.response_msg_type = response_msg_type

    async def payload_candidates(
            self,
            request: BaseRequest[TRequestPayload],
            timeout: int = None) -> 'AsyncGenerator[TResponsePayload, None]':
        """
        Make a request and iterate through candidates for a valid response.

        To mark a response as valid, use `complete_request`. After that call, payload
        candidates will stop arriving.
        """
        if timeout is None:
            timeout = self.response_timout

        self._request(request)
        while self._is_pending():
            yield await self._get_payload(timeout)

    @property
    def response_msg_name(self) -> str:
        return self.response_msg_type.__name__

    def complete_request(self, item_count: int) -> None:
        self.pending_request = None
        self.response_times.add(self.last_response_time, item_count)

    #
    # Service API
    #
    async def _run(self) -> None:
        self.logger.debug("Launching %s for peer %s", self.__class__.__name__, self._peer)

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
        future.set_result(msg)

    async def _get_payload(self, timeout: int) -> TResponsePayload:
        send_time, future = self.pending_request
        try:
            payload = await self.wait(future, timeout=timeout)
        except TimeoutError:
            self.response_times.total_timeouts += 1
            raise
        finally:
            self.pending_request = None

        # payload might be invalid, so prepare for another call to _get_payload()
        self.pending_request = (send_time, asyncio.Future())

        return payload

    def _request(self, request: BaseRequest[TRequestPayload]) -> None:
        if self.pending_request is not None:
            self.logger.error(
                "Already waiting for response to %s for peer: %s",
                self.response_msg_name,
                self._peer,
            )
            raise AlreadyWaiting(
                "Already waiting for response to {0} for peer: {1}".format(
                    self.response_msg_name,
                    self._peer
                )
            )

        self._peer.sub_proto.send_request(request)

        future: 'asyncio.Future[TResponsePayload]' = asyncio.Future()
        self.pending_request = (time.perf_counter(), future)

    def _is_pending(self) -> bool:
        return self.pending_request is not None

    async def _cleanup(self) -> None:
        if self.pending_request is not None:
            self.logger.debug("Stream shutting down, raising an exception on the pending request")
            _, future = self.pending_request
            future.set_exception(PeerConnectionLost("Pending request can't complete: peer is gone"))

    def deregister_peer(self, peer: BasePeer) -> None:
        if self.pending_request is not None:
            self.logger.debug("Peer disconnected, raising an exception on the pending request")
            _, future = self.pending_request
            future.set_exception(PeerConnectionLost("Pending request can't complete: peer is gone"))

    def get_stats(self) -> Tuple[str, str]:
        return (self.response_msg_name, self.response_times.get_stats())

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

    async def launch_service(self) -> None:
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
            timeout: int = None) -> TResult:

        if not self.is_operational:
            raise ValidationError("You must call `launch_service` before initiating a peer request")

        stream = self._response_stream

        async for payload in stream.payload_candidates(request, timeout):
            try:
                payload_validator(payload)

                if normalizer.is_normalization_slow:
                    result = await stream._run_in_executor(normalizer.normalize_result, payload)
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
                continue
            else:
                num_items = normalizer.get_num_results(result)
                stream.complete_request(num_items)
                return result

        raise ValidationError("Manager is not pending a response, but no valid response received")

    @property
    def service(self) -> BaseService:
        """
        This service that needs to be running for calls to execute properly
        """
        return self._response_stream

    def get_stats(self) -> Tuple[str, str]:
        if self._response_stream is None:
            return (self._response_command_type.__name__, 'Uninitialized')
        else:
            return self._response_stream.get_stats()
