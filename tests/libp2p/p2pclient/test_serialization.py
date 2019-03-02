import io

import pytest

from libp2p.p2pclient.serialization import (
    read_unsigned_varint,
    write_unsigned_varint,
)


pairs_int_varint_valid = (
    (0, b'\x00'),
    (1, b'\x01'),
    (128, b'\x80\x01'),
    (2 ** 32, b'\x80\x80\x80\x80\x10'),
    (2 ** 64 - 1, b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\x01'),
)

pairs_int_varint_overflow = (
    (2 ** 64, b'\x80\x80\x80\x80\x80\x80\x80\x80\x80\x02'),
    (2 ** 64 + 1, b'\x81\x80\x80\x80\x80\x80\x80\x80\x80\x02'),
    (2 ** 128, b'\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x80\x04'),
)


class MockReaderWriter(io.BytesIO):
    async def readexactly(self, n):
        return self.read(n)


@pytest.mark.parametrize(
    "integer, var_integer",
    pairs_int_varint_valid,
)
def test_write_unsigned_varint(integer, var_integer):
    s = MockReaderWriter()
    write_unsigned_varint(s, integer)
    assert s.getvalue() == var_integer


@pytest.mark.parametrize(
    "integer",
    tuple(i[0] for i in pairs_int_varint_overflow),
)
@pytest.mark.asyncio
async def test_write_unsigned_varint_overflow(integer):
    s = MockReaderWriter()
    with pytest.raises(ValueError):
        write_unsigned_varint(s, integer)


@pytest.mark.parametrize(
    "integer",
    (-1, -2**32, -2**64, -2**128),
)
@pytest.mark.asyncio
async def test_write_unsigned_varint_negative(integer):
    s = MockReaderWriter()
    with pytest.raises(ValueError):
        write_unsigned_varint(s, integer)


@pytest.mark.parametrize(
    "integer, var_integer",
    pairs_int_varint_valid,
)
@pytest.mark.asyncio
async def test_read_unsigned_varint(integer, var_integer):
    s = MockReaderWriter(var_integer)
    result = await read_unsigned_varint(s)
    assert result == integer


@pytest.mark.parametrize(
    "var_integer",
    tuple(i[1] for i in pairs_int_varint_overflow),
)
@pytest.mark.asyncio
async def test_read_unsigned_varint_overflow(var_integer):
    s = MockReaderWriter(var_integer)
    with pytest.raises(ValueError):
        await read_unsigned_varint(s)


@pytest.mark.parametrize(
    "max_bits",
    (2, 31, 32, 63, 64, 127, 128),
)
@pytest.mark.asyncio
async def test_read_write_unsigned_varint_max_bits_edge(max_bits):
    """
    Test the edge with different `max_bits`
    """
    for i in range(-3, 0):
        integer = i + (2 ** max_bits)
        s = MockReaderWriter()
        write_unsigned_varint(s, integer, max_bits=max_bits)
        s.seek(0, 0)
        result = await read_unsigned_varint(s, max_bits=max_bits)
        assert integer == result
