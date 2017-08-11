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
    code_stream = CodeStream(b'\x02\x60\x02\x04')
    assert code_stream.is_valid_opcode(0) is True  # x02
    assert code_stream.is_valid_opcode(1) is True  # x60
    assert code_stream.is_valid_opcode(2) is False  # x02
    assert code_stream.is_valid_opcode(3) is True  # x04
    assert code_stream.is_valid_opcode(4) is False  # too long


def test_harder_is_valid_opcode():
    code_stream = CodeStream(b'\x02\x03\x72' + (b'\x04' * 32) + b'\x05')
    # valid: 0-2
    # invalid: 3-21 #PUSH19
    # valid: 22-35
    # invalid: 36+ # too long
    assert code_stream.is_valid_opcode(0) is True
    assert code_stream.is_valid_opcode(1) is True
    assert code_stream.is_valid_opcode(2) is True
    assert code_stream.is_valid_opcode(3) is False
    assert code_stream.is_valid_opcode(21) is False
    assert code_stream.is_valid_opcode(22) is True
    assert code_stream.is_valid_opcode(35) is True
    assert code_stream.is_valid_opcode(36) is False


def test_even_harder_is_valid_opcode():
    test = b'\x02\x03\x7d' + (b'\x04' * 32) + b'\x05\x7e' + (b'\x04' * 35) + b'\x01\x61\x01\x01\x01'
    code_stream = CodeStream(test)
    # valid: 0-2
    # invalid: 3 - 32 # PUSH30
    # valid: 33 - 36
    # invalid: 37 - 67 # PUSH31
    # valid: 68 - 73
    # invalid: 74, 75 # PUSH2
    # valid: 76
    # invalid: 77+ # too long
    assert code_stream.is_valid_opcode(0) is True
    assert code_stream.is_valid_opcode(1) is True
    assert code_stream.is_valid_opcode(2) is True
    assert code_stream.is_valid_opcode(3) is False
    assert code_stream.is_valid_opcode(32) is False
    assert code_stream.is_valid_opcode(33) is True
    assert code_stream.is_valid_opcode(36) is True
    assert code_stream.is_valid_opcode(37) is False
    assert code_stream.is_valid_opcode(67) is False
    assert code_stream.is_valid_opcode(68) is True
    assert code_stream.is_valid_opcode(71) is True
    assert code_stream.is_valid_opcode(72) is True
    assert code_stream.is_valid_opcode(73) is True
    assert code_stream.is_valid_opcode(74) is False
    assert code_stream.is_valid_opcode(75) is False
    assert code_stream.is_valid_opcode(76) is True
    assert code_stream.is_valid_opcode(77) is False


def test_right_number_of_bytes_invalidated_after_pushxx():
    code_stream = CodeStream(b'\x02\x03\x60\x02\x02')
    assert code_stream.is_valid_opcode(0) is True
    assert code_stream.is_valid_opcode(1) is True
    assert code_stream.is_valid_opcode(2) is True
    assert code_stream.is_valid_opcode(3) is False
    assert code_stream.is_valid_opcode(4) is True
    assert code_stream.is_valid_opcode(5) is False
