from functools import partial
from typing import (
    AsyncIterator,
    Callable,
    Type,
)

from async_generator import asynccontextmanager

from p2p.abc import ConnectionAPI
from p2p.service import run_service

from .abc import ExchangeAPI, NormalizerAPI, ValidatorAPI
from .candidate_stream import ResponseCandidateStream
from .manager import ExchangeManager
from .typing import TResult, TRequestCommand, TResponseCommand


class BaseExchange(ExchangeAPI[TRequestCommand, TResponseCommand, TResult]):
    _request_command_type: Type[TRequestCommand]
    _response_command_type: Type[TResponseCommand]

    _manager: ExchangeManager[TRequestCommand, TResponseCommand, TResult]

    def __init__(self) -> None:
        self.tracker = self.tracker_class()

    @asynccontextmanager
    async def run_exchange(self, connection: ConnectionAPI) -> AsyncIterator[None]:
        protocol = connection.get_protocol_for_command_type(self.get_request_cmd_type())

        response_stream: ResponseCandidateStream[TRequestCommand, TResponseCommand] = ResponseCandidateStream(  # noqa: E501
            connection,
            protocol,
            self.get_response_cmd_type(),
        )
        self._manager = ExchangeManager(
            connection,
            response_stream,
        )
        async with run_service(response_stream):
            yield

    async def get_result(
            self,
            request: TRequestCommand,
            normalizer: NormalizerAPI[TResponseCommand, TResult],
            result_validator: ValidatorAPI[TResult],
            payload_validator: Callable[[TRequestCommand, TResponseCommand], None],
            timeout: float = None) -> TResult:
        """
        This is a light convenience wrapper around the ExchangeManager's get_result() method.

        It makes sure that:
        - the manager service is running
        - the payload validator is primed with the request payload
        """
        # bind the outbound request payload to the payload validator
        message_validator = partial(payload_validator, request.payload)

        return await self._manager.get_result(
            request,
            normalizer,
            result_validator.validate_result,
            message_validator,
            self.tracker,
            timeout,
        )

    @classmethod
    def get_response_cmd_type(cls) -> Type[TResponseCommand]:
        return cls._response_command_type

    @classmethod
    def get_request_cmd_type(cls) -> Type[TRequestCommand]:
        return cls._request_command_type

    @property
    def is_requesting(self) -> bool:
        return self._manager.is_requesting
