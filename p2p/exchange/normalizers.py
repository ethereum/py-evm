from .abc import NormalizerAPI
from .typing import TResponseCommand, TResult


class BaseNormalizer(NormalizerAPI[TResponseCommand, TResult]):
    is_normalization_slow = False
