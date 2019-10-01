from functools import partial
from typing import (
    AsyncIterator,
    Callable,
    Type,
)

from async_generator import asynccontextmanager

from p2p.abc import (
    CommandAPI,
    ConnectionAPI,
    RequestAPI,
)
from p2p.service import run_service
from p2p.typing import TRequestPayload, TResponsePayload

from .abc import ExchangeAPI, NormalizerAPI, ValidatorAPI
from .candidate_stream import ResponseCandidateStream
from .manager import ExchangeManager
from .typing import TResult


class BaseExchange(ExchangeAPI[TRequestPayload, TResponsePayload, TResult]):
    _manager: ExchangeManager[TRequestPayload, TResponsePayload, TResult]

    def __init__(self) -> None:
        self.tracker = self.tracker_class()

    @asynccontextmanager
    async def run_exchange(self, connection: ConnectionAPI) -> AsyncIterator[None]:
        protocol = connection.get_protocol_for_command_type(self.get_request_cmd_type())

        response_stream: ResponseCandidateStream[TRequestPayload, TResponsePayload] = ResponseCandidateStream(  # noqa: E501
            connection,
            protocol,
            self.get_response_cmd_type(),
        )

        try:
            self._manager = ExchangeManager(
                connection,
                response_stream,
            )
            async with run_service(response_stream):
                yield
        finally:
            del self._manager

    async def get_result(
            self,
            request: RequestAPI[TRequestPayload],
            normalizer: NormalizerAPI[TResponsePayload, TResult],
            result_validator: ValidatorAPI[TResult],
            payload_validator: Callable[[TRequestPayload, TResponsePayload], None],
            timeout: float = None) -> TResult:
        """
        This is a light convenience wrapper around the ExchangeManager's get_result() method.

        It makes sure that:
        - the manager service is running
        - the payload validator is primed with the request payload
        """
        # bind the outbound request payload to the payload validator
        message_validator = partial(payload_validator, request.command_payload)

        return await self._manager.get_result(
            request,
            normalizer,
            result_validator.validate_result,
            message_validator,
            self.tracker,
            timeout,
        )

    @classmethod
    def get_response_cmd_type(cls) -> Type[CommandAPI]:
        return cls.request_class.response_type

    @classmethod
    def get_request_cmd_type(cls) -> Type[CommandAPI]:
        return cls.request_class.cmd_type

    @property
    def is_requesting(self) -> bool:
        return self._manager.is_requesting
