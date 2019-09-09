from typing import cast

from p2p.typing import TResponsePayload

from .abc import NormalizerAPI
from .typing import TResult


class BaseNormalizer(NormalizerAPI[TResponsePayload, TResult]):
    is_normalization_slow = False


class NoopNormalizer(BaseNormalizer[TResponsePayload, TResult]):
    @staticmethod
    def normalize_result(message: TResponsePayload) -> TResult:
        return cast(TResult, message)
