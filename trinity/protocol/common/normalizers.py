from abc import abstractmethod, ABC

from typing import (
    Generic,
    Sized,
    TypeVar,
)

from .types import (
    TMsg,
    TResult,
)


class BaseNormalizer(ABC, Generic[TMsg, TResult]):
    is_normalization_slow = False
    """
    This variable indicates how slow normalization is. If normalization requires
    any non-trivial computation, consider it slow. Then, the Manager will run it in
    a different process.
    """

    @staticmethod
    @abstractmethod
    def normalize_result(message: TMsg) -> TResult:
        """
        Convert underlying peer message to final result
        """
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def get_num_results(result: TResult) -> int:
        """
        Count the number of items returned in the result.
        """
        raise NotImplementedError()


TPassthrough = TypeVar('TPassthrough', bound=Sized)


class NoopNormalizer(BaseNormalizer[TPassthrough, TPassthrough]):
    @staticmethod
    def normalize_result(message: TPassthrough) -> TPassthrough:
        return message

    @staticmethod
    def get_num_results(result: TPassthrough) -> int:
        return len(result)
