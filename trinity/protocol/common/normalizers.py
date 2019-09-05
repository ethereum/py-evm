from abc import abstractmethod, ABC
from typing import (
    Generic,
    TypeVar,
    cast,
)

from p2p.protocol import Payload

from .types import (
    TResponsePayload,
    TResult,
)


class BaseNormalizer(ABC, Generic[TResponsePayload, TResult]):
    is_normalization_slow = False
    """
    This variable indicates how slow normalization is. If normalization requires
    any non-trivial computation, consider it slow. Then, the Manager will run it in
    a different process.
    """

    @staticmethod
    @abstractmethod
    def normalize_result(message: TResponsePayload) -> TResult:
        """
        Convert underlying peer message to final result
        """
        ...


TPassthrough = TypeVar('TPassthrough', bound=Payload)


class NoopNormalizer(BaseNormalizer[TResponsePayload, TResult]):
    @staticmethod
    def normalize_result(message: TResponsePayload) -> TResult:
        return cast(TResult, message)
