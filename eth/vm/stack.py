import logging
from typing import (
    Any,
    Iterable,
    List,
    Tuple,
    Union,
)

from eth_utils import (
    ValidationError,
    big_endian_to_int,
    int_to_big_endian,
)

from eth.abc import (
    StackAPI,
)
from eth.exceptions import (
    FullStack,
    InsufficientStack,
)
from eth.validation import (
    validate_stack_bytes,
    validate_stack_int,
)


def _busted_type(value: Union[int, bytes]) -> ValidationError:
    item_type = type(value)
    return ValidationError(
        f"Stack must always be bytes or int, got {item_type!r} type, val {value!r}"
    )


class Stack(StackAPI):
    """
    VM Stack
    """

    __slots__ = ["values", "_append", "_pop_typed", "__len__"]
    logger = logging.getLogger("eth.vm.stack.Stack")

    #
    # Performance Note: Operations that push to the stack have the data in some natural
    #   form: integer or bytes. Whatever operation is pulling from the stack, also has
    #   its preferred representation to work with. Typically, those two representations
    #   line up (pushed & pulled) so we save a notable amount of conversion time by
    #   storing heterogenous data on the stack, and converting only when necessary.
    #

    def __init__(self) -> None:
        values: List[Union[int, bytes]] = []
        self.values = values
        # caching optimizations to avoid an attribute lookup on self.values
        # This doesn't use `cached_property`, because it doesn't play nice with slots
        self._append = values.append
        self._pop = values.pop
        self.__len__ = values.__len__

    def push_int(self, value: int) -> None:
        if len(self.values) > 1023:
            raise FullStack("Stack limit reached")

        validate_stack_int(value)

        self._append(value)

    def push_bytes(self, value: bytes) -> None:
        if len(self.values) > 1023:
            raise FullStack("Stack limit reached")

        validate_stack_bytes(value)

        self._append(value)

    def pop1_bytes(self) -> bytes:
        #
        # Note: This function is optimized for speed over readability.
        # Knowing the popped type means that we can pop *very* quickly
        # when the popped type matches the pushed type.
        #
        return to_bytes(self.pop1_any())

    def pop1_int(self) -> int:
        #
        # Note: This function is optimized for speed over readability.
        #
        return to_int(self.pop1_any())

    def pop1_any(self) -> Union[int, bytes]:
        #
        # Note: This function is optimized for speed over readability.
        #
        try:
            return self._pop()
        except IndexError:
            raise InsufficientStack("Wanted 1 stack item, had none")

    def pop_any(self, num_items: int) -> Tuple[Union[int, bytes], ...]:
        #
        # Note: This function is optimized for speed over readability.
        #
        if num_items > len(self.values):
            raise InsufficientStack(
                f"Wanted {num_items} stack items, only had {len(self.values)}"
            )

        # Quickest way to pop off multiple values from the end, in place
        ret = reversed(self.values[-num_items:])
        del self.values[-num_items:]

        return tuple(ret)

    def pop_ints(self, num_items: int) -> Tuple[int, ...]:
        return tuple(to_int(x) for x in self.pop_any(num_items))

    def pop_bytes(self, num_items: int) -> Tuple[bytes, ...]:
        return tuple(to_bytes(x) for x in self.pop_any(num_items))

    def swap(self, position: int) -> None:
        idx = -1 * position - 1
        try:
            self.values[-1], self.values[idx] = self.values[idx], self.values[-1]
        except IndexError:
            raise InsufficientStack(f"Insufficient stack items for SWAP{position}")

    def dup(self, position: int) -> None:
        if len(self.values) > 1023:
            raise FullStack("Stack limit reached")

        try:
            self._append(self.values[-position])
        except IndexError:
            raise InsufficientStack(f"Insufficient stack items for DUP{position}")

    def _stack_items_str(self) -> Iterable[str]:
        for val in self.values:
            if isinstance(val, int):
                yield hex(val)
            elif isinstance(val, bytes):
                yield "0x" + val.hex()
            else:
                raise RuntimeError(
                    f"Stack items can only be int or bytes, not {val!r}:{type(val)}"
                )

    def __str__(self) -> str:
        return str(list(self._stack_items_str()))


def to_int(x: Any) -> int:
    if isinstance(x, int):
        return x
    if isinstance(x, bytes):
        return big_endian_to_int(x)
    raise _busted_type(x)


def to_bytes(x: Any) -> bytes:
    if isinstance(x, bytes):
        return x
    if isinstance(x, int):
        return int_to_big_endian(x)
    raise _busted_type(x)
