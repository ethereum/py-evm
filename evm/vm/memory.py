import itertools
import logging

from evm.validation import (
    validate_is_bytes,
    validate_length,
    validate_lte,
    validate_uint256,
)

from evm.utils.numeric import (
    ceil32,
)


class Memory(object):
    """
    VM Memory
    """
    bytes = None
    logger = logging.getLogger('evm.vm.memory.Memory')

    def __init__(self):
        self.bytes = bytearray()

    def extend(self, start_position, size):
        if size == 0:
            return

        new_size = ceil32(start_position + size)
        if new_size <= len(self):
            return

        size_to_extend = new_size - len(self)
        self.bytes.extend(itertools.repeat(0, size_to_extend))

    def __len__(self):
        return len(self.bytes)

    def write(self, start_position, size, value):
        """
        Write `value` into memory.
        """
        if size:
            validate_uint256(start_position)
            validate_uint256(size)
            validate_is_bytes(value)
            validate_length(value, length=size)
            validate_lte(start_position + size, maximum=len(self))

            if len(self.bytes) < start_position + size:
                self.bytes.extend(itertools.repeat(
                    0,
                    len(self.bytes) - (start_position + size),
                ))

            for idx, v in enumerate(value):
                self.bytes[start_position + idx] = v

    def read(self, start_position, size):
        """
        Read a value from memory.
        """
        return bytes(self.bytes[start_position:start_position + size])
