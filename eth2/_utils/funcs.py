"""
A collection of helpful functions.
"""

from typing import Any


def constantly(x: Any) -> Any:
    """
    Return a function that returns ``x`` given any arguments.
    """
    def f(*args: Any, **kwargs: Any) -> Any:
        return x
    return f
