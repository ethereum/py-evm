import contextlib
import io
import logging

from evm import opcode_values
from evm.validation import (
    validate_is_bytes,
)


class CodeStream(object):
    stream = None
    deepest = None

    logger = logging.getLogger('evm.vm.CodeStream')

    def __init__(self, code_bytes):
        validate_is_bytes(code_bytes)
        self.stream = io.BytesIO(code_bytes)
        self._validity_cache = set(range(0))
        self.deepest = 0

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
        # if position longer than bytecode return false
        if position >= len(self):
            return False
        
        # return false if position already in val_cache
        if position in self._validity_cache: 
            return False
        # return true if position not in val_cache but has been parsed
        if position <= self.deepest: 
            return True
        else:
            # set counter to deepest parsed position
            i = self.deepest
            while i <= position:
                # get opcode 
                with self.seek(i):
                    opcode = self.next()
                # if opcode = pushxx
                if opcode >= opcode_values.PUSH1 and opcode <= opcode_values.PUSH32:
                    # add range(xx) to val_cache
                    self._validity_cache.update(range((i+1), ((i+1) + (opcode - 95))))
                    # increment counter to end of invalid bytes
                    i += (1 + (opcode - 95))
                else:
                    # if opcode != pushxx : update deepest processed and increment counter
                    self.deepest = i
                    i += 1
            
            if position in self._validity_cache:
                return False
            else:
                return True
