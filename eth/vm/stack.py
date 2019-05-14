import logging

from eth_utils import (
    big_endian_to_int,
    int_to_big_endian,
    ValidationError,
)
from eth.exceptions import (
    InsufficientStack,
    FullStack,
)
from eth.validation import (
    validate_stack_bytes,
    validate_stack_int,
)

from typing import (  # noqa: F401
    Generator,
    List,
    Tuple,
    Union
)
from eth_typing import Hash32  # noqa: F401


def _busted_type(item_type: type, value: Union[int, bytes]) -> ValidationError:
    return ValidationError(
        "Stack must always be bytes or int, got {!r} type, val {!r}".format(
            item_type,
            value,
        )
    )


class Stack(object):
    """
    VM Stack
    """
    __slots__ = ['values', '_append', '_pop_typed', '__len__']
    logger = logging.getLogger('eth.vm.stack.Stack')

    #
    # Performance Note: Operations that push to the stack have the data in some natural form:
    #   integer or bytes. Whatever operation is pulling from the stack, also has its preferred
    #   representation to work with. Typically, those two representations line up (pushed & pulled)
    #   so we save a notable amount of conversion time by storing heterogenous data on the stack,
    #   and converting only when necessary.
    #

    def __init__(self) -> None:
        values = []  # type: List[Tuple[type, Union[int, bytes]]]
        self.values = values
        # caching optimizations to avoid an attribute lookup on self.values
        # This doesn't use `cached_property`, because it doesn't play nice with slots
        self._append = values.append
        self._pop_typed = values.pop
        self.__len__ = values.__len__

    def push_int(self, value: int) -> None:
        """
        Push an integer item onto the stack.
        """
        if len(self.values) > 1023:
            raise FullStack('Stack limit reached')

        validate_stack_int(value)

        self._append((int, value))

    def push_bytes(self, value: bytes) -> None:
        """
        Push a bytes item onto the stack.
        """
        if len(self.values) > 1023:
            raise FullStack('Stack limit reached')

        validate_stack_bytes(value)

        self._append((bytes, value))

    def pop1_bytes(self) -> bytes:
        """
        Pop and return a bytes element from the stack.

        Raise `eth.exceptions.InsufficientStack` if the stack was empty.
        """

        #
        # Note: This function is optimized for speed over readability.
        # Knowing the popped type means that we can pop *very* quickly
        # when the popped type matches the pushed type.
        #
        if not self.values:
            raise InsufficientStack(
                "Wanted 1 stack item, only had %d",
                len(self.values),
            )
        else:
            item_type, popped = self._pop_typed()
            if item_type is int:
                return int_to_big_endian(popped)  # type: ignore
            elif item_type is bytes:
                return popped  # type: ignore
            else:
                raise _busted_type(item_type, popped)

    def pop1_int(self) -> int:
        """
        Pop and return an integer from the stack.

        Raise `eth.exceptions.InsufficientStack` if the stack was empty.
        """

        #
        # Note: This function is optimized for speed over readability.
        #
        if not self.values:
            raise InsufficientStack(
                "Wanted 1 stack item, only had %d",
                len(self.values),
            )
        else:
            item_type, popped = self._pop_typed()
            if item_type is int:
                return popped  # type: ignore
            elif item_type is bytes:
                return big_endian_to_int(popped)  # type: ignore
            else:
                raise _busted_type(item_type, popped)

    def pop1_any(self) -> Union[int, bytes]:
        """
        Pop and return an element from the stack.
        The type of each element will be int or bytes, depending on whether it was
        pushed with push_bytes or push_int.

        Raise `eth.exceptions.InsufficientStack` if the stack was empty.
        """

        #
        # Note: This function is optimized for speed over readability.
        #
        if not self.values:
            raise InsufficientStack(
                "Wanted 1 stack item, only had %d",
                len(self.values),
            )
        else:
            _, popped = self._pop_typed()
            return popped

    def pop_any(self, num_items: int) -> Tuple[Union[int, bytes], ...]:
        """
        Pop and return a tuple of items of length ``num_items`` from the stack.
        The type of each element will be int or bytes, depending on whether it was
        pushed with stack_push_bytes or stack_push_int.

        Raise `eth.exceptions.InsufficientStack` if there are not enough items on
        the stack.

        Items are ordered with the top of the stack as the first item in the tuple.
        """

        #
        # Note: This function is optimized for speed over readability.
        #
        if num_items > len(self.values):
            raise InsufficientStack(
                "Wanted %d stack items, only had %d",
                num_items,
                len(self.values),
            )
        else:
            neg_num_items = -1 * num_items

            # Quickest way to pop off multiple values from the end, in place
            all_popped = reversed(self.values[neg_num_items:])
            del self.values[neg_num_items:]

            # This doesn't use the @to_tuple(generator) pattern, for added performance
            return tuple(val for _, val in all_popped)

    def pop_ints(self, num_items: int) -> Tuple[int, ...]:
        """
        Pop and return a tuple of integers of length ``num_items`` from the stack.

        Raise `eth.exceptions.InsufficientStack` if there are not enough items on
        the stack.

        Items are ordered with the top of the stack as the first item in the tuple.
        """

        #
        # Note: This function is optimized for speed over readability.
        #
        if num_items > len(self.values):
            raise InsufficientStack(
                "Wanted %d stack items, only had %d",
                num_items,
                len(self.values),
            )
        else:
            neg_num_items = -1 * num_items

            # Quickest way to pop off multiple values from the end, in place
            all_popped = reversed(self.values[neg_num_items:])
            del self.values[neg_num_items:]

            type_cast_popped = []

            # Convert any non-matching types to the requested type (int)
            # This doesn't use the @to_tuple(generator) pattern, for added performance
            for item_type, popped in all_popped:
                if item_type is int:
                    type_cast_popped.append(popped)
                elif item_type is bytes:
                    type_cast_popped.append(big_endian_to_int(popped))  # type: ignore
                else:
                    raise _busted_type(item_type, popped)

            return tuple(type_cast_popped)  # type: ignore

    def pop_bytes(self, num_items: int) -> Tuple[bytes, ...]:
        """
        Pop and return a tuple of bytes of length ``num_items`` from the stack.

        Raise `eth.exceptions.InsufficientStack` if there are not enough items on
        the stack.

        Items are ordered with the top of the stack as the first item in the tuple.
        """

        #
        # Note: This function is optimized for speed over readability.
        #
        if num_items > len(self.values):
            raise InsufficientStack(
                "Wanted %d stack items, only had %d",
                num_items,
                len(self.values),
            )
        else:
            neg_num_items = -1 * num_items

            all_popped = reversed(self.values[neg_num_items:])
            del self.values[neg_num_items:]

            type_cast_popped = []

            # Convert any non-matching types to the requested type (int)
            # This doesn't use the @to_tuple(generator) pattern, for added performance
            for item_type, popped in all_popped:
                if item_type is int:
                    type_cast_popped.append(int_to_big_endian(popped))  # type: ignore
                elif item_type is bytes:
                    type_cast_popped.append(popped)  # type: ignore
                else:
                    raise _busted_type(item_type, popped)

            return tuple(type_cast_popped)

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
        if len(self.values) > 1023:
            raise FullStack('Stack limit reached')

        peek_index = -1 * position
        try:
            self._append(self.values[peek_index])
        except IndexError:
            raise InsufficientStack("Insufficient stack items for DUP{0}".format(position))
