"""
A collection of helpful functions.
"""

from typing import Any, Iterable


def constantly(x: Any) -> Any:
    """
    Return a function that returns ``x`` given any arguments.
    """
    def f(*args: Any, **kwargs: Any) -> Any:
        return x
    return f


def forever(x: Any) -> Iterable[Any]:
    """
    Returns an infinite stream of ``x``.

    Like ``constantly`` as an iterator.
    """
    while True:
        yield x
