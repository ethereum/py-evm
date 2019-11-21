import asyncio
import time
from typing import (
    Any,
    AsyncIterator,
    Tuple,
    Type,
)

from p2p.abc import (
    ConnectionAPI,
    ProtocolAPI,
)
from p2p.exceptions import (
    ConnectionBusy,
    PeerConnectionLost,
)
from p2p.service import BaseService

from .abc import (
    PerformanceTrackerAPI,
    ResponseCandidateStreamAPI,
)
from .constants import (
    ROUND_TRIP_TIMEOUT,
    NUM_QUEUED_REQUESTS,
)
from .typing import (
    TRequestCommand,
    TResponseCommand,
)


class ResponseCandidateStream(
        ResponseCandidateStreamAPI[TRequestCommand, TResponseCommand],
        BaseService):
    response_timeout: float = ROUND_TRIP_TIMEOUT

    pending_request: Tuple[float, 'asyncio.Future[TResponseCommand]'] = None

    def __init__(
            self,
            connection: ConnectionAPI,
            request_protocol: ProtocolAPI,
            response_cmd_type: Type[TResponseCommand]) -> None:
        # This style of initialization keeps `mypy` happy.
        BaseService.__init__(self, token=connection.cancel_token)

        self._connection = connection
        self.request_protocol = request_protocol
        self.response_cmd_type = response_cmd_type
        self._lock = asyncio.Lock()

    def __repr__(self) -> str:
        return f'<ResponseCandidateStream({self._connection!s}, {self.response_cmd_type!r})>'

    async def payload_candidates(
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
        total_timeout = self.response_timeout if timeout is None else timeout

        # The _lock ensures that we never have two concurrent requests to a
        # single peer for a single command pair in flight.
        try:
            await self.wait(self._lock.acquire(), timeout=total_timeout * NUM_QUEUED_REQUESTS)
        except asyncio.TimeoutError:
            raise ConnectionBusy(
                f"Timed out waiting for {self.response_cmd_name} request lock "
                f"or connection: {self._connection}"
            )

        start_at = time.perf_counter()

        try:
            self._request(request)
            while self.is_pending:
                timeout_remaining = max(0, total_timeout - (time.perf_counter() - start_at))

                try:
                    yield await self._get_payload(timeout_remaining)
                except asyncio.TimeoutError:
                    tracker.record_timeout(total_timeout)
                    raise
        finally:
            self._lock.release()

    @property
    def response_cmd_name(self) -> str:
        return self.response_cmd_type.__name__

    def complete_request(self) -> None:
        if self.pending_request is None:
            self.logger.warning("`complete_request` was called when there was no pending request")
        self.pending_request = None

    #
    # Service API
    #
    async def _run(self) -> None:
        self.logger.debug("Launching %r", self)

        # mypy doesn't recognizet the `TResponseCommand` as being an allowed
        # variant of the expected `Payload` type.
        with self._connection.add_command_handler(self.response_cmd_type, self._handle_msg):  # type: ignore  # noqa: E501
            await self.cancellation()

    async def _handle_msg(self, connection: ConnectionAPI, cmd: TResponseCommand) -> None:
        if self.pending_request is None:
            self.logger.debug(
                "Got unexpected %s payload from %s", self.response_cmd_name, self._connection
            )
            return

        send_time, future = self.pending_request
        self.last_response_time = time.perf_counter() - send_time
        try:
            future.set_result(cmd)
        except asyncio.InvalidStateError:
            self.logger.debug(
                "%s received a message response, but future was already done",
                self,
            )

    async def _get_payload(self, timeout: float) -> TResponseCommand:
        send_time, future = self.pending_request
        try:
            payload = await self.wait(future, timeout=timeout)
        finally:
            self.pending_request = None

        # payload might be invalid, so prepare for another call to _get_payload()
        self.pending_request = (send_time, asyncio.Future())

        return payload

    def _request(self, request: TRequestCommand) -> None:
        if not self._lock.locked():
            # This is somewhat of an invariant check but since there the
            # linkage between the lock and this method are loose this sanity
            # check seems appropriate.
            raise Exception("Invariant: cannot issue a request without an acquired lock")

        # TODO: better API for getting at the protocols from the connection....
        self.request_protocol.send(request)

        future: 'asyncio.Future[TResponseCommand]' = asyncio.Future()
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
