import contextlib
import io
import logging
from typing import (  # noqa: F401
    Iterator,
    Set
)

from eth.validation import (
    validate_is_bytes,
)
from eth.vm import opcode_values


class CodeStream(object):
    stream = None
    depth_processed = None
    _length_cache = None
    _raw_code_bytes = None

    logger = logging.getLogger('eth.vm.CodeStream')

    def __init__(self, code_bytes: bytes) -> None:
        validate_is_bytes(code_bytes, title="CodeStream bytes")
        self.stream = io.BytesIO(code_bytes)
        self._raw_code_bytes = code_bytes
        self._length_cache = len(code_bytes)
        self.invalid_positions = set()  # type: Set[int]
        self.depth_processed = 0

    def read(self, size: int) -> bytes:
        return self.stream.read(size)

    def __len__(self) -> int:
        return self._length_cache

    def __iter__(self) -> 'CodeStream':
        return self

    def __next__(self) -> int:
        return self._next()

    def __getitem__(self, i: int) -> int:
        return self._raw_code_bytes[i]

    def _next(self) -> int:
        next_opcode_as_byte = self.read(1)

        if next_opcode_as_byte:
            return ord(next_opcode_as_byte)
        else:
            return opcode_values.STOP

    def peek(self) -> int:
        current_pc = self.pc
        next_opcode = next(self)
        self.pc = current_pc
        return next_opcode

    @property
    def pc(self) -> int:
        return self.stream.tell()

    @pc.setter
    def pc(self, value: int) -> None:
        self.stream.seek(min(value, len(self)))

    @contextlib.contextmanager
    def seek(self, pc: int) -> Iterator['CodeStream']:
        anchor_pc = self.pc
        self.pc = pc
        try:
            yield self
        finally:
            self.pc = anchor_pc

    invalid_positions = None

    def is_valid_opcode(self, position: int) -> bool:
        if position >= self._length_cache:
            return False
        if position in self.invalid_positions:
            return False
        if position <= self.depth_processed:
            return True
        else:
            i = self.depth_processed
            while i <= position:
                opcode = self.__getitem__(i)
                if opcode >= opcode_values.PUSH1 and opcode <= opcode_values.PUSH32:
                    left_bound = (i + 1)
                    right_bound = left_bound + (opcode - 95)
                    invalid_range = range(left_bound, right_bound)
                    self.invalid_positions.update(invalid_range)
                    i = right_bound
                else:
                    self.depth_processed = i
                    i += 1

            if position in self.invalid_positions:
                return False
            else:
                return True
