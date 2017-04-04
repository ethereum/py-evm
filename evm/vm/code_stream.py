import contextlib
import io
import logging

from evm import opcode_values
from evm.validation import (
    validate_is_bytes,
)


class CodeStream(object):
    stream = None

    logger = logging.getLogger('evm.vm.CodeStream')

    def __init__(self, code_bytes):
        validate_is_bytes(code_bytes)
        self.stream = io.BytesIO(code_bytes)
        self._validity_cache = {}

    def read(self, size):
        return self.stream.read(size)

    def __len__(self):
        return len(self.stream.getvalue())

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

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
        except:
            raise
        finally:
            self.pc = anchor_pc

    _validity_cache = None

    def is_valid_opcode(self, position):
        if position >= len(self):
            return False

        if position not in self._validity_cache:
            with self.seek(max(0, position - 32)):
                prefix = self.read(min(position, 32))

            for offset, opcode in enumerate(reversed(prefix)):
                if opcode < opcode_values.PUSH1 or opcode > opcode_values.PUSH32:
                    continue

                push_size = 1 + opcode - opcode_values.PUSH1
                if push_size <= offset:
                    continue

                opcode_position = position - 1 - offset
                if not self.is_valid_opcode(opcode_position):
                    continue

                self._validity_cache[position] = False
                break
            else:
                self._validity_cache[position] = True

        return self._validity_cache[position]
