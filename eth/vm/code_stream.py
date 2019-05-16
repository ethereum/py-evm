import contextlib
from typing import (  # noqa: F401
    Iterator,
    Set
)

from eth_utils import HasLogger

from eth.validation import (
    validate_is_bytes,
)
from eth.vm import opcode_values

PUSH1, PUSH32, STOP = opcode_values.PUSH1, opcode_values.PUSH32, opcode_values.STOP


class CodeStream(HasLogger):
    __slots__ = ['_length_cache', '_raw_code_bytes', 'invalid_positions', 'valid_positions', 'pc']

    def __init__(self, code_bytes: bytes) -> None:
        validate_is_bytes(code_bytes, title="CodeStream bytes")
        # in order to avoid method overhead when setting/accessing pc, we no longer fence
        # the pc (Program Counter) into 0 <= pc <= len(code_bytes). We now let it float free.
        # NOTE: Setting pc to a negative value has undefined behavior.
        self.pc = 0
        self._raw_code_bytes = code_bytes
        self._length_cache = len(code_bytes)
        self.invalid_positions = set()  # type: Set[int]
        self.valid_positions = set()  # type: Set[int]

    def read(self, size: int) -> bytes:
        old_pc = self.pc
        target_pc = old_pc + size
        self.pc = target_pc
        return self._raw_code_bytes[old_pc:target_pc]

    def __len__(self) -> int:
        return self._length_cache

    def __getitem__(self, i: int) -> int:
        return self._raw_code_bytes[i]

    def __iter__(self) -> Iterator[int]:
        # a very performance-sensitive method
        pc = self.pc
        while pc < self._length_cache:
            opcode = self._raw_code_bytes[pc]
            self.pc = pc + 1
            yield opcode
            # a read might have adjusted the pc during the last yield
            pc = self.pc

        yield STOP

    def peek(self) -> int:
        pc = self.pc
        if pc < self._length_cache:
            return self._raw_code_bytes[pc]
        else:
            return STOP

    @contextlib.contextmanager
    def seek(self, pc: int) -> Iterator['CodeStream']:
        anchor_pc = self.pc
        self.pc = pc
        try:
            yield self
        finally:
            self.pc = anchor_pc

    def _potentially_disqualifying_opcode_positions(self, position: int) -> Iterator[int]:
        # Look at the last 32 positions (from 1 byte back to 32 bytes back).
        # Don't attempt to look at negative positions.
        deepest_lookback = min(32, position)
        # iterate in reverse, because PUSH32 is more common than others
        for bytes_back in range(deepest_lookback, 0, -1):
            earlier_position = position - bytes_back
            opcode = self._raw_code_bytes[earlier_position]
            if PUSH1 + (bytes_back - 1) <= opcode <= PUSH32:
                # that PUSH1, if two bytes back, isn't disqualifying
                # PUSH32 in any of the bytes back is disqualifying
                yield earlier_position

    def is_valid_opcode(self, position: int) -> bool:
        if position >= self._length_cache:
            return False
        elif position in self.invalid_positions:
            return False
        elif position in self.valid_positions:
            return True
        else:
            # An opcode is not valid, iff it is the "data" following a PUSH_
            # So we look at the previous 32 bytes (PUSH32 being the largest) to see if there
            # is a PUSH_ before the opcode in this position.
            for disqualifier in self._potentially_disqualifying_opcode_positions(position):
                # Now that we found a PUSH_ before this position, we check if *that* PUSH is valid
                if self.is_valid_opcode(disqualifier):
                    # If the PUSH_ valid, then the current position is invalid
                    self.invalid_positions.add(position)
                    return False
                # Otherwise, keep looking for other potentially disqualifying PUSH_ codes

            # We didn't find any valid PUSH_ opcodes in the 32 bytes before position; it's valid
            self.valid_positions.add(position)
            return True
