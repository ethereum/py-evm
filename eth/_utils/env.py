"""
This module is copied from https://github.com/simpleenergy/env-excavator,
which is helpful for extracting environment variables.
"""

import os
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Type,
    TypeVar,
    Union,
)

# No set literals because we support Python 2.6.
TRUE_VALUES = {
    True,
    "True",
    "true",
}


class empty:
    """
    We use this sentinel object, instead of None, as None is a plausible value
    for a default in real Python code.
    """


def get_env_value(name: str, required: bool = False, default: Any = empty) -> str:
    """
    Core function for extracting the environment variable.

    Enforces mutual exclusivity between `required` and `default` keywords.

    The `empty` sentinal value is used as the default `default` value to allow
    other function to handle default/empty logic in the appropriate way.
    """
    if required and default is not empty:
        raise ValueError("Using `default` with `required=True` is invalid")
    elif required:
        try:
            value = os.environ[name]
        except KeyError:
            raise KeyError(f"Must set environment variable {name}")
    else:
        value = os.environ.get(name, default)
    return value


def env_int(
    name: str, required: bool = False, default: Union[Type[empty], int] = empty
) -> int:
    """
    Pulls an environment variable out of the environment and casts it to an
    integer. If the name is not present in the environment and no default is
    specified then a ``ValueError`` will be raised. Similarly, if the
    environment value is not castable to an integer, a ``ValueError`` will be
    raised.

    :param name: The name of the environment variable be pulled
    :type name: str

    :param required: Whether the environment variable is required. If ``True``
    and the variable is not present, a ``KeyError`` is raised.
    :type required: bool

    :param default: The value to return if the environment variable is not
    present. (Providing a default alongside setting ``required=True`` will raise
    a ``ValueError``)
    :type default: bool
    """
    value = get_env_value(name, required=required, default=default)
    if value is empty:
        raise ValueError(
            "`env_int` requires either a default value to be specified, or for "
            "the variable to be present in the environment"
        )
    return int(value)


def env_float(
    name: str, required: bool = False, default: Union[Type[empty], float] = empty
) -> float:
    """
    Pulls an environment variable out of the environment and casts it to an
    float. If the name is not present in the environment and no default is
    specified then a ``ValueError`` will be raised. Similarly, if the
    environment value is not castable to an float, a ``ValueError`` will be
    raised.

    :param name: The name of the environment variable be pulled
    :type name: str

    :param required: Whether the environment variable is required. If ``True``
    and the variable is not present, a ``KeyError`` is raised.
    :type required: bool

    :param default: The value to return if the environment variable is not
    present. (Providing a default alongside setting ``required=True`` will raise
    a ``ValueError``)
    :type default: bool
    """
    value = get_env_value(name, required=required, default=default)
    if value is empty:
        raise ValueError(
            "`env_float` requires either a default value to be specified, or for "
            "the variable to be present in the environment"
        )
    return float(value)


def env_bool(
    name: str,
    truthy_values: Iterable[Any] = TRUE_VALUES,
    required: bool = False,
    default: Union[Type[empty], bool] = empty,
) -> bool:
    """
    Pulls an environment variable out of the environment returning it as a
    boolean. The strings ``'True'`` and ``'true'`` are the default *truthy*
    values. If not present in the environment and no default is specified,
    ``None`` is returned.

    :param name: The name of the environment variable be pulled
    :type name: str

    :param truthy_values: An iterable of values that should be considered
    truthy.
    :type truthy_values: iterable

    :param required: Whether the environment variable is required. If ``True``
    and the variable is not present, a ``KeyError`` is raised.
    :type required: bool

    :param default: The value to return if the environment variable is not
    present. (Providing a default alongside setting ``required=True`` will raise
    a ``ValueError``)
    :type default: bool
    """
    value = get_env_value(name, required=required, default=default)
    if value is empty:
        return None
    return value in TRUE_VALUES


def env_string(
    name: str, required: bool = False, default: Union[Type[empty], str] = empty
) -> str:
    """
    Pulls an environment variable out of the environment returning it as a
    string. If not present in the environment and no default is specified, an
    empty string is returned.

    :param name: The name of the environment variable be pulled
    :type name: str

    :param required: Whether the environment variable is required. If ``True``
    and the variable is not present, a ``KeyError`` is raised.
    :type required: bool

    :param default: The value to return if the environment variable is not
    present. (Providing a default alongside setting ``required=True`` will raise
    a ``ValueError``)
    :type default: bool
    """
    value = get_env_value(name, default=default, required=required)
    if value is empty:
        value = ""
    return value


def env_list(
    name: str,
    separator: str = ",",
    required: bool = False,
    default: Union[Type[empty], List[Any]] = empty,
) -> List[Any]:
    """
    Pulls an environment variable out of the environment, splitting it on a
    separator, and returning it as a list. Extra whitespace on the list values
    is stripped. List values that evaluate as falsy are removed. If not present
    and no default specified, an empty list is returned.

    :param name: The name of the environment variable be pulled
    :type name: str

    :param separator: The separator that the string should be split on.
    :type separator: str

    :param required: Whether the environment variable is required. If ``True``
    and the variable is not present, a ``KeyError`` is raised.
    :type required: bool

    :param default: The value to return if the environment variable is not
    present. (Providing a default alongside setting ``required=True`` will raise
    a ``ValueError``)
    :type default: bool
    """
    value = get_env_value(name, required=required, default=default)
    if value is empty:
        return []
    # wrapped in list to force evaluation in python 3
    return list(filter(bool, [v.strip() for v in value.split(separator)]))


T = TypeVar("T")


def get(
    name: str,
    required: bool = False,
    default: Union[Type[empty], T] = empty,
    type: Type[T] = None,
) -> T:
    """
    Generic getter for environment variables. Handles defaults,
    required-ness, and what type to expect.

    :param name: The name of the environment variable be pulled
    :type name: str

    :param required: Whether the environment variable is required. If ``True``
    and the variable is not present, a ``KeyError`` is raised.
    :type required: bool

    :param default: The value to return if the environment variable is not
    present. (Providing a default alongside setting ``required=True`` will raise
    a ``ValueError``)
    :type default: bool

    :param type: The type of variable expected.
    :param type: str or type
    """
    fns: Dict[Union[str, Type[Any]], Callable[..., Any]] = {
        "int": env_int,
        int: env_int,
        # 'float': env_float,
        # float: env_float,
        "bool": env_bool,
        bool: env_bool,
        "string": env_string,
        str: env_string,
        "list": env_list,
        list: env_list,
    }

    fn = fns.get(type, env_string)
    return fn(name, default=default, required=required)
