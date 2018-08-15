import asyncio
import time
from typing import (
    Any,
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

from p2p.peer import BasePeer, PeerSubscriber
from p2p.protocol import (
    BaseRequest,
    Command,
)
from p2p.service import BaseService

from trinity.exceptions import AlreadyWaiting

from .normalizers import BaseNormalizer
from .types import (
    TCommandPayload,
    TMsg,
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


class MessageManager(PeerSubscriber, BaseService, Generic[TMsg]):

    #
    # PeerSubscriber
    #
    @property
    def subscription_msg_types(self) -> Set[Type[Command]]:
        return {self._response_msg_type}

    msg_queue_maxsize = 100

    response_timout: int = 60

    pending_request: Tuple[float, 'asyncio.Future[TMsg]'] = None

    _peer: BasePeer

    def __init__(
            self,
            peer: BasePeer,
            response_msg_type: Type[Command],
            token: CancelToken) -> None:
        super().__init__(token)
        self._peer = peer
        self.response_times = ResponseTimeTracker()
        self._response_msg_type = response_msg_type

    async def message_candidates(
            self,
            request: BaseRequest[Any],
            timeout: int) -> 'AsyncGenerator[TMsg, None]':
        """
        Make a request and iterate through candidates for a valid response.

        To mark a response as valid, use `complete_request`. After that call, message
        candidates will stop arriving.
        """
        self._request(request)
        while self._is_pending():
            yield await self._get_message(timeout)

    @property
    def response_msg_name(self) -> str:
        return self._response_msg_type.__name__

    def complete_request(self, item_count: int) -> None:
        self.pending_request = None
        self.response_times.add(self.last_response_time, item_count)

    #
    # Service API
    #
    async def _run(self) -> None:
        self.logger.debug("Launching %s for peer %s", self.__class__.__name__, self._peer)

        with self.subscribe_peer(self._peer):
            while not self.cancel_token.triggered:
                peer, cmd, msg = await self.wait(self.msg_queue.get())
                if peer != self._peer:
                    self.logger.error("Unexpected peer: %s  expected: %s", peer, self._peer)
                    continue
                elif isinstance(cmd, self._response_msg_type):
                    await self._handle_msg(cast(TMsg, msg))
                else:
                    self.logger.warning("Unexpected message type: %s", cmd.__class__.__name__)

    async def _handle_msg(self, msg: TMsg) -> None:
        if self.pending_request is None:
            self.logger.debug(
                "Got unexpected %s message from %", self.response_msg_name, self._peer
            )
            return

        send_time, future = self.pending_request
        self.last_response_time = time.perf_counter() - send_time
        future.set_result(msg)

    async def _get_message(self, timeout: int) -> TMsg:
        send_time, future = self.pending_request
        try:
            message = await self.wait(future, timeout=timeout)
        except TimeoutError:
            self.response_times.total_timeouts += 1
            self.pending_request = None
            raise
        else:
            # message might be invalid, so allow another attempt to wait for a valid response
            self.pending_request = (send_time, asyncio.Future())

        return message

    def _request(self, request: BaseRequest[Any]) -> None:
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

        future: 'asyncio.Future[TMsg]' = asyncio.Future()
        self.pending_request = (time.perf_counter(), future)

    def _is_pending(self) -> bool:
        return self.pending_request is not None

    def get_stats(self) -> str:
        return '%s: %s' % (self.response_msg_name, self.response_times.get_stats())


class ExchangeManager(Generic[TCommandPayload, TMsg, TResult]):
    _message_manager: MessageManager[TMsg] = None

    def __init__(
            self,
            peer: BasePeer,
            cancel_token: CancelToken) -> None:
        self._peer = peer
        self._cancel_token = cancel_token

    async def launch_service(self, listening_for: Type[Command]) -> None:
        self._message_manager = MessageManager(
            self._peer,
            listening_for,
            self._cancel_token,
        )
        self._peer.run_daemon(self._message_manager)
        await self._message_manager.events.started.wait()

    @property
    def is_running(self) -> bool:
        return self.service is not None and self.service.is_running

    async def get_result(
            self,
            request: BaseRequest[TCommandPayload],
            normalizer: BaseNormalizer[TMsg, TResult],
            validate_result: Callable[[TResult], None],
            message_validator: Callable[[TMsg], None] = None,
            timeout: int = None) -> TResult:

        if not self.is_running:
            raise ValidationError("You must call `launch_service` before initiating a peer request")

        manager = self._message_manager

        async for message in manager.message_candidates(request, timeout):
            try:
                if message_validator is not None:
                    message_validator(message)

                if normalizer.is_normalization_slow:
                    result = await manager._run_in_executor(normalizer.normalize_result, message)
                else:
                    result = normalizer.normalize_result(message)

                validate_result(result)
            except ValidationError as err:
                self.service.logger.debug(
                    "Response validation failed for pending %s request from peer %s: %s",
                    manager.response_msg_name,
                    self._peer,
                    err,
                )
                continue
            else:
                num_items = normalizer.get_num_results(result)
                manager.complete_request(num_items)
                return result

        raise ValidationError("Manager is not pending a response, but no valid response received")

    @property
    def service(self) -> BaseService:
        """
        This service that needs to be running for calls to execute properly
        """
        return self._message_manager

    def get_stats(self) -> str:
        return self._message_manager.get_stats()
