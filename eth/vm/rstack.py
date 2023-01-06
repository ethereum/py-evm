from typing import (
    List,
    Tuple,
    Union,
)

from eth.exceptions import (
    InsufficientStack,
    FullStack,
)

from eth.validation import (
    validate_stack_int,
)

from eth_utils import (
    big_endian_to_int,
    ValidationError,
)

"""
This module simply implements for the return stack the exact same design used for the data stack.
As this stack must simply push_int or pop1_int any time a subroutine is accessed or left, only
those two functions are provided.
For the same reason, the class RStack doesn't inherit from the abc StackAPI, as it would require
to implement all the abstract methods defined.
"""


class RStack:
    """
    VM Return Stack
    """

    __slots__ = ['values', '_append', '_pop_typed', '__len__']

    def __init__(self) -> None:
        values: List[Tuple[type, Union[int, bytes]]] = []
        self.values = values
        self._append = values.append
        self._pop_typed = values.pop
        self.__len__ = values.__len__

    def push_int(self, value: int) -> None:
        if len(self.values) > 1023:
            raise FullStack('Stack limit reached')

        validate_stack_int(value)

        self._append((int, value))

    def pop1_int(self) -> int:
        #
        # Note: This function is optimized for speed over readability.
        #
        if not self.values:
            raise InsufficientStack("Wanted 1 stack item as int, had none")
        else:
            item_type, popped = self._pop_typed()
            if item_type is int:
                return popped  # type: ignore
            elif item_type is bytes:
                return big_endian_to_int(popped)  # type: ignore
            else:
                raise ValidationError(
                    "Stack must always be bytes or int, "
                    f"got {item_type!r} type"
                )
