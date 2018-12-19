from abc import ABC, abstractmethod
from functools import partial
from typing import (
    Any,
    Callable,
    Generic,
    Type,
)

from p2p.protocol import (
    BaseRequest,
    Command,
    TRequestPayload,
)

from trinity._utils.decorators import classproperty
from .trackers import (
    BasePerformanceTracker,
)
from .managers import (
    ExchangeManager,
)
from .normalizers import BaseNormalizer
from .types import (
    TResponsePayload,
    TResult,
)
from .validators import BaseValidator


class BaseExchange(ABC, Generic[TRequestPayload, TResponsePayload, TResult]):
    """
    The exchange object handles a few things, in rough order:

     - convert from friendly input arguments to the protocol arguments
     - generate the appropriate BaseRequest object
     - identify the BaseNormalizer that can convert the response payload to the desired result
     - prepare the BaseValidator that can validate the final result against the requested data
     - (if necessary) prepare a response payload validator, which validates data that is *not*
        present in the final result
     - issue the request to the ExchangeManager, with the request, normalizer, and validators
     - await the normalized & validated response, and return it

    TRequestPayload is the data as passed directly to the p2p command
    TResponsePayload is the data as received directly from the p2p command response
    TResult is the response data after normalization
    """

    request_class: Type[BaseRequest[TRequestPayload]]
    tracker_class: Type[BasePerformanceTracker[Any, TResult]]
    tracker: BasePerformanceTracker[BaseRequest[TRequestPayload], TResult]

    def __init__(self, mgr: ExchangeManager[TRequestPayload, TResponsePayload, TResult]) -> None:
        self._manager = mgr
        self.tracker = self.tracker_class()

    async def get_result(
            self,
            request: BaseRequest[TRequestPayload],
            normalizer: BaseNormalizer[TResponsePayload, TResult],
            result_validator: BaseValidator[TResult],
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

    @classproperty
    def response_cmd_type(cls) -> Type[Command]:
        return cls.request_class.response_type

    @abstractmethod
    async def __call__(self, *args: Any, **kwargs: Any) -> None:
        """
        Issue the request to the peer for the desired data
        """
        raise NotImplementedError('__call__ must be defined on every Exchange')
