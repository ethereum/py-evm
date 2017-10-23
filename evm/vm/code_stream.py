import contextlib
import io
import logging

from evm import opcode_values
from evm.validation import (
    validate_is_bytes,
)


class CodeStream(object):
    stream = None
    depth_processed = None

    logger = logging.getLogger('evm.vm.CodeStream')

    def __init__(self, code_bytes):
        validate_is_bytes(code_bytes, title="CodeStream bytes")
        self.stream = io.BytesIO(code_bytes)
        self.invalid_positions = set()
        self.depth_processed = 0

    def read(self, size):
        return self.stream.read(size)

    def __len__(self):
        return len(self.stream.getvalue())

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    def __getitem__(self, i):
        return self.stream.getvalue()[i]

    def next(self):
        next_opcode_as_byte = self.read(1)

        if next_opcode_as_byte:
            return ord(next_opcode_as_byte)
        else:
            return opcode_values.STOP

    def peek(self):
        current_pc = self.pc
        next_opcode = next(self)
        self.pc = current_pc
        return next_opcode

    @property
    def pc(self):
        return self.stream.tell()

    @pc.setter
    def pc(self, value):
        self.stream.seek(min(value, len(self)))

    @contextlib.contextmanager
    def seek(self, pc):
        anchor_pc = self.pc
        self.pc = pc
        try:
            yield self
        finally:
            self.pc = anchor_pc

    invalid_positions = None

    def is_valid_opcode(self, position):
        if position >= len(self):
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
