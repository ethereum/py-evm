from typing import (
    Tuple,
    TypeVar,
)

from eth_utils import (
    ValidationError,
)


VType = TypeVar('VType')


def update_tuple_item(tuple_data: Tuple[VType, ...],
                      index: int,
                      new_value: VType) -> Tuple[VType, ...]:
    """
    Update the ``index``th item of ``tuple_data`` to ``new_value``
    """
    list_data = list(tuple_data)

    try:
        list_data[index] = new_value
    except IndexError:
        raise ValidationError(
            "the length of the given tuple_data is {}, the given index {} is out of index".format(
                len(tuple_data),
                index,
            )
        )
    else:
        return tuple(list_data)
