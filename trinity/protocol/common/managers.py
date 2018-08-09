from abc import abstractmethod
import asyncio
from typing import (
    Any,
    cast,
    Generic,
    Set,
    Tuple,
    Type,
    TypeVar,
)

from cancel_token import CancelToken

from p2p.exceptions import (
    MalformedMessage,
    ValidationError,
)
from p2p.p2p_proto import DisconnectReason
from p2p.peer import BasePeer, PeerSubscriber
from p2p.protocol import (
    Command,
)
from p2p.service import BaseService

from trinity.exceptions import AlreadyWaiting

from .requests import BaseRequest


# The peer class that this will be connected to
TPeer = TypeVar('TPeer', bound=BasePeer)
# The `Request` class that will be used.
TRequest = TypeVar('TRequest', bound=BaseRequest[Any, Any])
# The type that will be returned to the caller
TReturn = TypeVar('TReturn')
# The type of the command payload
TMsg = TypeVar('TMsg')


class BaseRequestManager(PeerSubscriber, BaseService, Generic[TPeer, TRequest, TMsg, TReturn]):  # noqa: E501
    #
    # PeerSubscriber
    #
    @property
    def subscription_msg_types(self) -> Set[Type[Command]]:
        return {self._response_msg_type}

    msg_queue_maxsize = 100

    response_timout: int = 60

    pending_request: Tuple[TRequest, 'asyncio.Future[TReturn]'] = None

    _peer: TPeer

    def __init__(self, peer: TPeer, token: CancelToken) -> None:
        self._peer = peer
        super().__init__(token)

    #
    # Service API
    #
    async def _run(self) -> None:
        self.logger.debug("Launching %s for peer %s", self.__class__.__name__, self._peer)

        with self.subscribe_peer(self._peer):
            while self.is_running:
                peer, cmd, msg = await self.wait(
                    self.msg_queue.get(), token=self.cancel_token)
                if peer != self._peer:
                    self.logger.error("Unexpected peer: %s  expected: %s", peer, self._peer)
                    continue
                elif isinstance(cmd, self._response_msg_type):
                    await self._handle_msg(cast(TMsg, msg))
                else:
                    self.logger.warning("Unexpected message type: %s", cmd.__class__.__name__)

    async def _cleanup(self) -> None:
        pass

    async def _handle_msg(self, msg: TMsg) -> None:
        if self.pending_request is None:
            self.logger.debug(
                "Got unexpected %s message from %", self.response_msg_name, self._peer
            )
            return

        request, future = self.pending_request

        try:
            response = await self._normalize_response(msg)
        except MalformedMessage as err:
            self.logger.warn(
                "Malformed response for pending %s request from peer %s, disconnecting: %s",
                self.response_msg_name,
                self._peer,
                err,
            )
            await self._peer.disconnect(DisconnectReason.bad_protocol)
            return

        try:
            request.validate_response(msg, response)
        except ValidationError as err:
            self.logger.debug(
                "Response validation failed for pending %s request from peer %s: %s",
                self.response_msg_name,
                self._peer,
                err,
            )
            return

        future.set_result(response)
        self.pending_request = None

    @abstractmethod
    async def _normalize_response(self, msg: TMsg) -> TReturn:
        pass

    @abstractmethod
    def __call__(self) -> TReturn:
        """
        Subclasses must both implement this method and override the call
        signature to properly construct the `Request` object and pass it into
        `get_from_peer`

        NOTE: It is expected that subclasses will override this method and
        change the signature.  The change in signature is expected to result in
        a type checking failure, and thus all subclasses will also be required
        to add an `# type: ignore` comment to make the type checker happy.
        """
        pass

    @property
    @abstractmethod
    def _response_msg_type(self) -> Type[Command]:
        pass

    @property
    def response_msg_name(self) -> str:
        return self._response_msg_type.__name__

    @abstractmethod
    def _send_sub_proto_request(self, request: TRequest) -> None:
        pass

    async def _wait_for_response(self,
                                 request: TRequest,
                                 timeout: int = None) -> TReturn:
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

        future: 'asyncio.Future[TReturn]' = asyncio.Future()
        self.pending_request = (request, future)

        try:
            response = await self.wait(future, timeout=timeout)
        finally:
            # Always ensure that we reset the `pending_request` to `None` on exit.
            self.pending_request = None

        return response

    async def _request_and_wait(self, request: TRequest, timeout: int=None) -> TReturn:
        if timeout is None:
            timeout = self.response_timout
        self._send_sub_proto_request(request)
        return await self._wait_for_response(request, timeout=timeout)
