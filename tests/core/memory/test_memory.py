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


@pytest.mark.parametrize("start_position,size,value", ((0, 4, b'1010'),))
def test_write(memory32, start_position, size, value):
    memory32.write(start_position, size, value)
    assert memory32.bytes == value + bytearray(32 - size)


@pytest.mark.parametrize("start_position,size,value", ((-1, 4, b'1010'),))
def test_write_rejects_invalid_start_position(memory32, start_position, size, value):
    with pytest.raises(ValidationError):
        memory32.write(start_position, size, value)


@pytest.mark.parametrize("start_position,size,value", ((0, 2**256, b'1010'),))
def test_write_rejects_invalid_size(memory32, start_position, size, value):
    with pytest.raises(ValidationError):
        memory32.write(start_position, size, value)


@pytest.mark.parametrize("start_position,size,value", ((0, 4, '1010'),))
def test_write_rejects_invalid_value(memory32, start_position, size, value):
    with pytest.raises(ValidationError):
        memory32.write(start_position, size, value)


@pytest.mark.parametrize("start_position,size,value", ((0, 5, '1010'),))
def test_write_rejects_size_not_equal_to_value_length(memory32, start_position, size, value):
    with pytest.raises(ValidationError):
        memory32.write(start_position, size, value)


@pytest.mark.parametrize("start_position,size,value", ((30, 4, b'1010'),))
def test_write_rejects_values_beyond_memory_size(memory32, start_position, size, value):
    with pytest.raises(ValidationError):
        memory32.write(start_position, size, value)


def test_extend_appropriately_extends_memory(memory):
    memory.extend(0, 32)
    assert memory.bytes == bytearray(32)
    memory.extend(30, 32)
    assert memory.bytes == bytearray(64)
    memory.extend(48, 10)
    assert memory.bytes == bytearray(64)
    memory.extend(60, 16)
    assert memory.bytes == bytearray(96)


@pytest.mark.parametrize("start_position,size,value", ((5, 4, b'1010'),))
def test_read_returns_correct_bytes_from_memory(memory32, start_position, size, value):
    memory32.write(start_position, size, value)
    assert memory32.read(start_position, size) == value
    assert memory32.read(start_position + 1, size) != value
    assert memory32.read(start_position, size + 1) != value
