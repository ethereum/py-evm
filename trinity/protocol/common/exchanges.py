from abc import ABC, abstractmethod
from functools import partial
from typing import (
    Any,
    Callable,
    Generic,
)

from p2p.protocol import (
    BaseRequest,
)

from .managers import ExchangeManager
from .normalizers import BaseNormalizer
from .types import (
    TCommandPayload,
    TMsg,
    TResult,
)
from .validators import BaseValidator


class BaseExchange(ABC, Generic[TCommandPayload, TMsg, TResult]):
    """
    The exchange object handles a few things, in rough order:

     - store the request_args from initialization for later use by a validator
     - convert from friendly input arguments to the protocol arguments
     - issue the protocol request
     - identify the Command type of the message that comes as a response to the request
     - convert from protocol response message to a friendly result (aka normalization)
     - identify whether normalization is slow
        (which is used to decide if it should be run in another process)
     - identify the validator class used to validate the response message and the normalized result

    The init function should take whatever arguments are used to send the request.
    """

    is_normalization_slow = False
    """
    This variable indicates how slow normalization is. If normalization requires
    any non-trivial computation, consider it slow. Then, the Manager will run it in
    a different process.
    """

    request_args: Any = None

    def __init__(self, manager: ExchangeManager[TCommandPayload, TMsg, TResult]) -> None:
        self._manager = manager

    async def get_result(
            self,
            request: BaseRequest[TCommandPayload],
            normalizer: BaseNormalizer[TMsg, TResult],
            result_validator: BaseValidator[TResult],
            command_validator: Callable[[TCommandPayload, TMsg], None] = None,
            timeout: int = None) -> TResult:

        """
        The type of message that the peer will send in response to this exchange's request
        """
        if not self._manager.is_running:
            await self._manager.launch_service(request.response_type)

        if command_validator is None:
            message_validator = None
        else:
            # bind the outbound request to the message validator
            message_validator = partial(command_validator, request.command_payload)

        return await self._manager.get_result(
            request,
            normalizer,
            result_validator.validate_result,
            message_validator,
        )

    @abstractmethod
    async def __call__(self, *args: Any, **kwargs: Any) -> None:
        """
        Issue the request to the peer for the desired data
        """
        raise NotImplementedError()
