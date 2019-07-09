from typing import (
    Any,
    Callable,
    Tuple,
    TypeVar,
)

from eth_utils import (
    ValidationError,
)


VType = TypeVar('VType')


def update_tuple_item_with_fn(tuple_data: Tuple[VType, ...],
                              index: int,
                              fn: Callable[[VType, Any], VType],
                              *args: Any) -> Tuple[VType, ...]:
    """
    Update the ``index``th item of ``tuple_data`` to the result of calling ``fn`` on the existing
    value.
    """
    list_data = list(tuple_data)

    try:
        old_value = list_data[index]
        list_data[index] = fn(old_value, *args)
    except IndexError:
        raise ValidationError(
            "the length of the given tuple_data is {}, the given index {} is out of index".format(
                len(tuple_data),
                index,
            )
        )
    else:
        return tuple(list_data)


def update_tuple_item(tuple_data: Tuple[VType, ...],
                      index: int,
                      new_value: VType) -> Tuple[VType, ...]:
    """
    Update the ``index``th item of ``tuple_data`` to ``new_value``
    """
    return update_tuple_item_with_fn(
        tuple_data,
        index,
        lambda *_: new_value
    )
