from functools import partial
from typing import (
    Callable,
    Type,
)

from p2p.abc import CommandAPI, RequestAPI
from p2p.typing import TRequestPayload, TResponsePayload

from .abc import ExchangeAPI, NormalizerAPI, ValidatorAPI
from .managers import ExchangeManager
from .typing import TResult


class BaseExchange(ExchangeAPI[TRequestPayload, TResponsePayload, TResult]):
    def __init__(self, mgr: ExchangeManager[TRequestPayload, TResponsePayload, TResult]) -> None:
        self._manager = mgr
        self.tracker = self.tracker_class()

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
        if not self._manager.is_operational:
            await self._manager.launch_service()

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
