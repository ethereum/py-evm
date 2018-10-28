import logging

from eth_utils import (
    int_to_big_endian,
    big_endian_to_int,
)
from eth import constants
from eth.exceptions import (
    InsufficientStack,
    FullStack,
)
from eth.validation import (
    validate_stack_item,
)

from typing import (  # noqa: F401
    Generator,
    List,
    Tuple,
    Union
)
from eth_typing import Hash32  # noqa: F401


class Stack(object):
    """
    VM Stack
    """
    __slots__ = ['values']
    logger = logging.getLogger('eth.vm.stack.Stack')

    def __init__(self) -> None:
        self.values = []  # type: List[Union[int, bytes]]

    def __len__(self) -> int:
        return len(self.values)

    def push(self, value: Union[int, bytes]) -> None:
        """
        Push an item onto the stack.
        """
        if len(self.values) > 1023:
            raise FullStack('Stack limit reached')

        validate_stack_item(value)

        self.values.append(value)

    def pop(self,
            num_items: int,
            type_hint: str) -> Union[int, bytes, Tuple[Union[int, bytes], ...]]:
        """
        Pop an item off the stack.

        Note: This function is optimized for speed over readability.
        """
        try:
            if num_items == 1:
                return next(self._pop(num_items, type_hint))
            else:
                return tuple(self._pop(num_items, type_hint))
        except IndexError:
            raise InsufficientStack("No stack items")

    def _pop(self, num_items: int, type_hint: str) -> Generator[Union[int, bytes], None, None]:
        for _ in range(num_items):
            if type_hint == constants.UINT256:
                value = self.values.pop()
                if isinstance(value, int):
                    yield value
                else:
                    yield big_endian_to_int(value)
            elif type_hint == constants.BYTES:
                value = self.values.pop()
                if isinstance(value, bytes):
                    yield value
                else:
                    yield int_to_big_endian(value)
            elif type_hint == constants.ANY:
                yield self.values.pop()
            else:
                raise TypeError(
                    "Unknown type_hint: {0}.  Must be one of {1}".format(
                        type_hint,
                        ", ".join((constants.UINT256, constants.BYTES)),
                    )
                )

    def swap(self, position: int) -> None:
        """
        Perform a SWAP operation on the stack.
        """
        idx = -1 * position - 1
        try:
            self.values[-1], self.values[idx] = self.values[idx], self.values[-1]
        except IndexError:
            raise InsufficientStack("Insufficient stack items for SWAP{0}".format(position))

    def dup(self, position: int) -> None:
        """
        Perform a DUP operation on the stack.
        """
        idx = -1 * position
        try:
            self.push(self.values[idx])
        except IndexError:
            raise InsufficientStack("Insufficient stack items for DUP{0}".format(position))
