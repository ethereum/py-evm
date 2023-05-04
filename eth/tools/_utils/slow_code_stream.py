import contextlib
import io
import logging
from typing import (
    Iterator,
    Set,
)

from eth.validation import (
    validate_is_bytes,
)
from eth.vm import (
    opcode_values,
)

PUSH1, PUSH32, STOP = opcode_values.PUSH1, opcode_values.PUSH32, opcode_values.STOP


class SlowCodeStream:
    """
    A known working version of code stream that is kept around for testing,
    despite not being optimized.
    """

    stream = None
    _length_cache = None
    _raw_code_bytes = None
    invalid_positions: Set[int] = None
    valid_positions: Set[int] = None

    logger = logging.getLogger("eth.vm.SlowCodeStream")

    def __init__(self, code_bytes: bytes) -> None:
        validate_is_bytes(code_bytes, title="SlowCodeStream bytes")
        stream = io.BytesIO(code_bytes)
        self.stream = stream
        self._bound_stream_read = stream.read
        self._raw_code_bytes = code_bytes
        self._length_cache = len(code_bytes)
        self.invalid_positions = set()
        self.valid_positions = set()

    def read(self, size: int) -> bytes:
        return self._bound_stream_read(size)

    def __len__(self) -> int:
        return self._length_cache

    def __getitem__(self, i: int) -> int:
        return self._raw_code_bytes[i]

    def __iter__(self) -> Iterator[int]:
        # a very performance-sensitive method
        read = self.read
        try:
            while True:
                yield ord(read(1))
        except TypeError:
            yield STOP

    def __next__(self) -> int:
        # a very performance-sensitive method
        next_opcode_as_byte = self._bound_stream_read(1)

        if next_opcode_as_byte:
            return ord(next_opcode_as_byte)
        else:
            return STOP

    def peek(self) -> int:
        current_pc = self.program_counter
        next_opcode = next(self)
        self.program_counter = current_pc
        return next_opcode

    @property
    def program_counter(self) -> int:
        return self.stream.tell()

    @program_counter.setter
    def program_counter(self, value: int) -> None:
        self.stream.seek(min(value, len(self)))

    @contextlib.contextmanager
    def seek(self, pc: int) -> Iterator["SlowCodeStream"]:
        anchor_pc = self.program_counter
        self.program_counter = pc
        try:
            yield self
        finally:
            self.program_counter = anchor_pc

    def _potentially_disqualifying_opcode_positions(
        self, position: int
    ) -> Iterator[int]:
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
            # So we look at the previous 32 bytes (PUSH32 being the largest) to see if
            # there is a PUSH_ before the opcode in this position.
            for disqualifier in self._potentially_disqualifying_opcode_positions(
                position
            ):
                # Now that we found a PUSH_ before this position, we check if *that* PUSH is valid  # noqa: E501
                if self.is_valid_opcode(disqualifier):
                    # If the PUSH_ valid, then the current position is invalid
                    self.invalid_positions.add(position)
                    return False
                # Otherwise, keep looking for other potentially disqualifying PUSH_ codes  # noqa: E501

            # We didn't find any valid PUSH_ opcodes in the 32 bytes before position;it's valid  # noqa: E501
            self.valid_positions.add(position)
            return True
