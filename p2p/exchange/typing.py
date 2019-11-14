from typing import Any, TypeVar

from p2p.abc import CommandAPI


TRequestCommand = TypeVar('TRequestCommand', bound=CommandAPI[Any])
TResponseCommand = TypeVar('TResponseCommand', bound=CommandAPI[Any])
TResult = TypeVar('TResult')
