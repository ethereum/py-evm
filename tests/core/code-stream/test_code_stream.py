import itertools
import sys

from eth_utils import (
    ValidationError,
)
from eth_utils.toolz import (
    drop,
)
from hypothesis import (
    given,
    strategies as st,
)
import pytest

from eth.tools._utils.slow_code_stream import (
    SlowCodeStream,
)
from eth.vm import (
    opcode_values,
)
from eth.vm.code_stream import (
    CodeStream,
)


def test_code_stream_accepts_bytes():
    code_stream = CodeStream(b"\x02")
    assert len(code_stream) == 1
    assert code_stream[0] == 2


@pytest.mark.parametrize("code_bytes", (1010, "1010", True, bytearray(32)))
def test_code_stream_rejects_invalid_code_byte_values(code_bytes):
    with pytest.raises(ValidationError):
        CodeStream(code_bytes)


def test_next_returns_the_correct_next_opcode():
    iterable = CodeStream(b"\x01\x02\x30")
    code_stream = iter(iterable)
    assert next(code_stream) == opcode_values.ADD
    assert next(code_stream) == opcode_values.MUL
    assert next(code_stream) == opcode_values.ADDRESS


def test_peek_returns_next_opcode_without_changing_code_stream_location():
    code_stream = CodeStream(b"\x01\x02\x30")
    code_iter = iter(code_stream)
    assert code_stream.program_counter == 0
    assert code_stream.peek() == opcode_values.ADD
    assert code_stream.program_counter == 0
    assert next(code_iter) == opcode_values.ADD
    assert code_stream.program_counter == 1
    assert code_stream.peek() == opcode_values.MUL
    assert code_stream.program_counter == 1


def test_STOP_opcode_is_returned_when_bytecode_end_is_reached():
    iterable = CodeStream(b"\x01\x02")
    code_stream = iter(iterable)
    next(code_stream)
    next(code_stream)
    assert next(code_stream) == opcode_values.STOP


def test_seek_reverts_to_original_stream_position_when_context_exits():
    code_stream = CodeStream(b"\x01\x02\x30")
    code_iter = iter(code_stream)
    assert code_stream.program_counter == 0
    with code_stream.seek(1):
        assert code_stream.program_counter == 1
        assert next(code_iter) == opcode_values.MUL
    assert code_stream.program_counter == 0
    assert code_stream.peek() == opcode_values.ADD


def test_get_item_returns_correct_opcode():
    code_stream = CodeStream(b"\x01\x02\x30")
    assert code_stream[0] == opcode_values.ADD
    assert code_stream[1] == opcode_values.MUL
    assert code_stream[2] == opcode_values.ADDRESS


def test_is_valid_opcode_invalidates_bytes_after_PUSHXX_opcodes():
    code_stream = CodeStream(b"\x02\x60\x02\x04")
    assert code_stream.is_valid_opcode(0) is True
    assert code_stream.is_valid_opcode(1) is True
    assert code_stream.is_valid_opcode(2) is False
    assert code_stream.is_valid_opcode(3) is True
    assert code_stream.is_valid_opcode(4) is False


def test_is_valid_opcode_valid_with_PUSH32_just_past_boundary():
    # valid: 0 :: 33
    # invalid: 1 - 32 (PUSH32) :: 34+ (too long)
    code_stream = CodeStream(b"\x7f" + (b"\0" * 32) + b"\x60")
    assert code_stream.is_valid_opcode(0) is True
    for pos in range(1, 33):
        assert code_stream.is_valid_opcode(pos) is False
    assert code_stream.is_valid_opcode(33) is True
    assert code_stream.is_valid_opcode(34) is False


def test_harder_is_valid_opcode():
    code_stream = CodeStream(b"\x02\x03\x72" + (b"\x04" * 32) + b"\x05")
    # valid: 0 - 2 :: 22 - 35
    # invalid: 3-21 (PUSH19) :: 36+ (too long)
    assert code_stream.is_valid_opcode(0) is True
    assert code_stream.is_valid_opcode(1) is True
    assert code_stream.is_valid_opcode(2) is True
    assert code_stream.is_valid_opcode(3) is False
    assert code_stream.is_valid_opcode(21) is False
    assert code_stream.is_valid_opcode(22) is True
    assert code_stream.is_valid_opcode(35) is True
    assert code_stream.is_valid_opcode(36) is False


def test_even_harder_is_valid_opcode():
    test = (
        b"\x02\x03\x7d"
        + (b"\x04" * 32)
        + b"\x05\x7e"
        + (b"\x04" * 35)
        + b"\x01\x61\x01\x01\x01"
    )
    code_stream = CodeStream(test)
    # valid: 0 - 2 :: 33 - 36 :: 68 - 73 :: 76
    # invalid: 3 - 32 (PUSH30) :: 37 - 67 (PUSH31) :: 74, 75 (PUSH2) :: 77+ (too long)
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


def test_even_harder_is_valid_opcode_first_check_deep():
    test = (
        b"\x02\x03\x7d"
        + (b"\x04" * 32)
        + b"\x05\x7e"
        + (b"\x04" * 35)
        + b"\x01\x61\x01\x01\x01"
    )
    code_stream = CodeStream(test)
    # valid: 0 - 2 :: 33 - 36 :: 68 - 73 :: 76
    # invalid: 3 - 32 (PUSH30) :: 37 - 67 (PUSH31) :: 74, 75 (PUSH2) :: 77+ (too long)
    assert code_stream.is_valid_opcode(75) is False


def test_right_number_of_bytes_invalidated_after_pushxx():
    code_stream = CodeStream(b"\x02\x03\x60\x02\x02")
    assert code_stream.is_valid_opcode(0) is True
    assert code_stream.is_valid_opcode(1) is True
    assert code_stream.is_valid_opcode(2) is True
    assert code_stream.is_valid_opcode(3) is False
    assert code_stream.is_valid_opcode(4) is True
    assert code_stream.is_valid_opcode(5) is False


ALL_SINGLE_BYTES = tuple(sorted(set(range(0, 256))))
PUSH_CODES = set(bytearray(range(96, 128)))
NON_PUSH_CODES = set(ALL_SINGLE_BYTES).difference(PUSH_CODES)


def _mk_bytecode(opcodes, data):
    index_tracker = itertools.count(0)
    for opcode in opcodes:
        opcode_as_byte = bytes((opcode,))
        if opcode in NON_PUSH_CODES:
            yield next(index_tracker), opcode_as_byte
        else:
            data_size = opcode - 95
            push_data = data.draw(st.binary(min_size=data_size, max_size=data_size))
            yield next(index_tracker), opcode_as_byte + push_data
            drop(data_size, index_tracker)


@given(
    opcodes=st.lists(st.sampled_from(ALL_SINGLE_BYTES), min_size=0, max_size=2048),
    data=st.data(),
)
def test_fuzzy_is_valid_opcode(opcodes, data):
    if opcodes:
        indices, bytecode_sections = zip(*_mk_bytecode(opcodes, data))
        bytecode = b"".join(bytecode_sections)
    else:
        indices = set()
        bytecode = b""

    valid_indices = set(indices)

    stream = CodeStream(bytecode)

    index_st = st.integers(min_value=0, max_value=len(bytecode) + 10)
    to_check = data.draw(st.lists(index_st, max_size=len(bytecode)))
    for index in to_check:
        is_valid = stream.is_valid_opcode(index)
        expected = index in valid_indices
        assert is_valid is expected


@given(bytecode=st.binary(max_size=2048))
def test_new_vs_reference_code_stream_iter(bytecode):
    reference = SlowCodeStream(bytecode)
    latest = CodeStream(bytecode)
    for expected_op, actual_op in zip(reference, latest):
        assert expected_op == actual_op
        assert reference.program_counter == latest.program_counter

    assert latest.program_counter == reference.program_counter


@given(
    read_len=st.integers(min_value=0, max_value=sys.maxsize),
    bytecode=st.binary(max_size=128),
)
def test_new_vs_reference_code_stream_read(read_len, bytecode):
    reference = SlowCodeStream(bytecode)
    latest = CodeStream(bytecode)
    readout_expected = reference.read(read_len)
    readout_actual = latest.read(read_len)
    assert readout_expected == readout_actual
    if read_len <= len(bytecode):
        assert latest.program_counter == reference.program_counter
    assert latest.read(1) == reference.read(1)


@given(
    read_idx=st.integers(min_value=0, max_value=10),
    read_len=st.integers(min_value=0, max_value=sys.maxsize),
    bytecode=st.binary(max_size=128),
)
def test_new_vs_reference_code_stream_read_during_iter(read_idx, read_len, bytecode):
    reference = SlowCodeStream(bytecode)
    latest = CodeStream(bytecode)
    for index, (actual, expected) in enumerate(zip(latest, reference)):
        assert actual == expected
        if index == read_idx:
            readout_actual = latest.read(read_len)
            readout_expected = reference.read(read_len)
            assert readout_expected == readout_actual
        if reference.program_counter >= len(reference):
            assert latest.program_counter >= len(reference)
        else:
            assert latest.program_counter == reference.program_counter
