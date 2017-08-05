import pytest

from evm import opcode_values
from evm.vm.code_stream import (
    CodeStream,
)
from evm.exceptions import (
    ValidationError,
)


def test_code_stream_accepts_bytes():
    code_stream = CodeStream(b'\x01')
    assert len(code_stream.stream.getvalue()) == 1


@pytest.mark.parametrize("code_bytes", (1010, '1010', True, bytearray(32)))
def test_code_stream_rejects_invalid_code_byte_values(code_bytes):
    with pytest.raises(ValidationError):
        CodeStream(code_bytes)


def test_next_returns_the_correct_next_opcode():
    code_stream = CodeStream(b'\x01\x02\x30')
    assert code_stream.next() == opcode_values.ADD
    assert next(code_stream) == opcode_values.MUL
    assert code_stream.next() == opcode_values.ADDRESS


def test_peek_returns_next_opcode_without_changing_code_stream_location():
    code_stream = CodeStream(b'\x01\x02\x30')
    assert code_stream.pc == 0
    assert code_stream.peek() == opcode_values.ADD
    assert code_stream.pc == 0
    assert code_stream.next() == opcode_values.ADD
    assert code_stream.pc == 1
    assert code_stream.peek() == opcode_values.MUL
    assert code_stream.pc == 1


def test_STOP_opcode_is_returned_when_bytecode_end_is_reached():
    code_stream = CodeStream(b'\x01\x02')
    code_stream.next()
    code_stream.next()
    assert code_stream.next() == opcode_values.STOP


def test_seek_reverts_to_original_stream_position_when_context_exits():
    code_stream = CodeStream(b'\x01\x02\x30')
    assert code_stream.pc == 0
    with code_stream.seek(1):
        assert code_stream.pc == 1
        assert code_stream.next() == opcode_values.MUL
    assert code_stream.pc == 0
    assert code_stream.peek() == opcode_values.ADD


def test_is_valid_opcode_invalidates_bytes_after_PUSHXX_opcodes():
    code_stream = CodeStream(b'\x01\x60\x02')
    assert code_stream.is_valid_opcode(0) is True
    assert code_stream.is_valid_opcode(1) is True
    assert code_stream.is_valid_opcode(2) is False
