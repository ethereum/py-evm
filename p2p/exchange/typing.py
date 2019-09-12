from typing import Any, TypeVar

from p2p.abc import RequestAPI


TRequest = TypeVar('TRequest', bound=RequestAPI[Any])
TResponse = TypeVar('TResponse')
TResult = TypeVar('TResult')
