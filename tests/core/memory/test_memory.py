from eth_utils import (
    ValidationError,
)
import pytest

from eth.vm.memory import (
    Memory,
)


@pytest.fixture
def memory():
    return Memory()


@pytest.fixture
def memory32():
    memory = Memory()
    memory.extend(0, 32)
    return memory


def test_write(memory32):
    # Test that write creates 32byte string == value padded with zeros
    memory32.write(start_position=0, size=4, value=b"1010")
    assert memory32._bytes == b"1010" + bytearray(28)


@pytest.mark.parametrize("start_position", (-1, 2**256, "a", b"1010"))
def test_write_rejects_invalid_start_position(memory32, start_position):
    with pytest.raises(ValidationError):
        memory32.write(start_position=start_position, size=4, value=b"1010")


@pytest.mark.parametrize("size", (-1, 2**256, "a", b"1010"))
def test_write_rejects_invalid_size(memory32, size):
    with pytest.raises(ValidationError):
        memory32.write(start_position=0, size=size, value=b"1010")


@pytest.mark.parametrize("value", ("1010", 1234, True))
def test_write_rejects_invalid_value(memory32, value):
    with pytest.raises(ValidationError):
        memory32.write(start_position=0, size=4, value=value)


def test_write_rejects_size_not_equal_to_value_length(memory32):
    with pytest.raises(ValidationError):
        memory32.write(start_position=0, size=5, value=b"1010")


def test_write_rejects_values_beyond_memory_size(memory32):
    with pytest.raises(ValidationError):
        memory32.write(start_position=30, size=4, value=b"1010")


def test_extend_appropriately_extends_memory(memory):
    # Test extends to 32 byte array: 0 < (start_position + size) <= 32
    memory.extend(start_position=0, size=10)
    assert memory._bytes == bytearray(32)
    # Test will extend past length if params require: 32 < (start_position + size) <= 64
    memory.extend(start_position=30, size=32)
    assert memory._bytes == bytearray(64)
    # Test won't extend past length unless params require: 32 < (start_position + size) <= 64  # noqa: E501
    memory.extend(start_position=48, size=10)
    assert memory._bytes == bytearray(64)


def test_read_returns_correct_bytes_from_memory(memory32):
    memory32.write(start_position=5, size=4, value=b"1010")
    assert memory32.read(start_position=5, size=4) == b"1010"
    assert memory32.read(start_position=6, size=4) != b"1010"
    assert memory32.read(start_position=5, size=5) != b"1010"
