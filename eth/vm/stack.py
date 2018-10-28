import logging

from eth_utils import (
    int_to_big_endian,
    big_endian_to_int,
)
from eth.exceptions import (
    InsufficientStack,
    FullStack,
)
from eth.validation import (
    validate_stack_item,
)

from typing import (  # noqa: F401
    List,
    Union
)
from eth_typing import Hash32  # noqa: F401


class Stack(object):
    """
    VM Stack
    """
    __slots__ = ['values']
    logger = logging.getLogger('eth.vm.stack.Stack')

    def __init__(self):
        self.values = []  # type: List[int]

    def __len__(self):
        return len(self.values)

    def push(self, value):
        """
        Push an item onto the stack.
        bytes are converted to int before pushing
        """
        if len(self.values) > 1023:
            raise FullStack('Stack limit reached')

        if isinstance(value, int):
            stack_item = value
        elif isinstance(value, bytes):
            stack_item = big_endian_to_int(value)
        else:
            stack_item = value

        validate_stack_item(stack_item)

        self.values.append(stack_item)

    def pop_ints(self, num_items):
        """
        Pop items off the stack and return as integers.
        """
        if len(self.values) < num_items:
            raise InsufficientStack("No stack items")

        for _ in range(num_items):
            yield self.values.pop()

    def pop_bytes(self, num_items):
        """
        Pop items off the stack and return as bytes.
        """
        if len(self.values) < num_items:
            raise InsufficientStack("No stack items")

        for _ in range(num_items):
            stack_item = self.values.pop()
            yield int_to_big_endian(stack_item)

    def swap(self, position):
        """
        Perform a SWAP operation on the stack.
        """
        idx = -1 * position - 1
        try:
            self.values[-1], self.values[idx] = self.values[idx], self.values[-1]
        except IndexError:
            raise InsufficientStack("Insufficient stack items for SWAP{0}".format(position))

    def dup(self, position):
        """
        Perform a DUP operation on the stack.
        """
        idx = -1 * position
        try:
            self.push(self.values[idx])
        except IndexError:
            raise InsufficientStack("Insufficient stack items for DUP{0}".format(position))
