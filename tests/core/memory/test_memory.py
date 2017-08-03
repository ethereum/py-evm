import pytest

from evm.vm.memory import (
    Memory,
)
from evm.exceptions import (
    ValidationError,
)


@pytest.fixture
def memory():
    return Memory()


@pytest.fixture
def memory32():
    memory = Memory()
    memory.extend(0, 32)
    return memory


@pytest.mark.parametrize(
    "start_position,size,value,is_valid",
    (
        (0, 4, b'1010', True),
        ('a', 4, b'1010', False),
        (0, 'a', b'1010', False),
        (-1, 4, b'1010', False),
        (0, -1, b'1010', False),
        (2**256, 4, b'1010', False),
        (0, 2**256, b'1010', False),
    )
)
def test_start_position_and_size_valid_on_write(memory32, start_position, size, value, is_valid):
    if is_valid:
        memory32.write(start_position, size, value)
        assert memory32.bytes == value + bytearray(b'\x00\x00') * 14
    else:
        with pytest.raises(ValidationError):
            memory32.write(start_position, size, value)


@pytest.mark.parametrize(
    "start_position,size,value,is_valid",
    (
        (0, 4, b'1010', True),
        (0, 4, '1010', False),
        (0, 4, 1234, False),
        (0, 4, True, False),
    )
)
def test_value_is_bytes_on_write(memory32, start_position, size, value, is_valid):
    if is_valid:
        memory32.write(start_position, size, value)
        assert memory32.bytes == value + bytearray(b'\x00\x00') * 14
    else:
        with pytest.raises(ValidationError):
            memory32.write(start_position, size, value)


@pytest.mark.parametrize(
    "start_position,size,value,is_valid",
    (
        (0, 4, b'1010', True),
        (5, 3, b'1010', False),
        (10, 5, b'1010', False),
    )
)
def test_value_length_equals_size_on_write(memory32, start_position, size, value, is_valid):
    if is_valid:
        memory32.write(start_position, size, value)
        assert memory32.bytes == value + bytearray(b'\x00\x00') * 14
    else:
        with pytest.raises(ValidationError):
            memory32.write(start_position, size, value)


@pytest.mark.parametrize(
    "start_position,size,value,is_valid",
    (
        (0, 4, b'1010', True),
        (30, 4, b'1010', False),
    )
)
def test_write_cant_extend_beyond_memory_size(memory32, start_position, size, value, is_valid):
    if is_valid:
        memory32.write(start_position, size, value)
        assert memory32.bytes == value + bytearray(b'\x00\x00') * 14
    else:
        with pytest.raises(ValidationError):
            memory32.write(start_position, size, value)


def test_extend_appropriately_extends_memory(memory):
    memory.extend(0, 32)
    assert memory.bytes == bytearray(b'\x00\x00') * 16
    memory.extend(30, 32)
    assert memory.bytes == bytearray(b'\x00\x00') * 32
    memory.extend(48, 10)
    assert memory.bytes == bytearray(b'\x00\x00') * 32
    memory.extend(60, 16)
    assert memory.bytes == bytearray(b'\x00\x00') * 48


@pytest.mark.parametrize(
    "start_position,size,value",
    (
        (0, 4, b'1010'),
        (10, 10, b'1010101010'),
    )
)
def test_read_returns_correct_bytes_from_memory(memory32, start_position, size, value):
    memory32.write(start_position, size, value)
    assert memory32.read(start_position, size) == value
    assert memory32.read(start_position + 1, size) != value
    assert memory32.read(start_position, size + 1) != value
