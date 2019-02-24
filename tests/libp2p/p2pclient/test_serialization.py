import io

import pytest


from libp2p.p2pclient.serialization import (
    read_varint,
    write_varint,
)


def test_serialize():
    pass


def test_pb_readwriter():
    pass


@pytest.mark.parametrize(
    "value, expected_result",
    (
        (0, b'\x00'),
        (1, b'\x01'),
        (128, b'\x80\x01'),
        (2 ** 32, b'\x80\x80\x80\x80\x10'),
        (2 ** 64 - 1, b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\x01'),
    ),
)
def test_write_varint(value, expected_result):
    s0 = io.BytesIO()
    write_varint(s0, value)
    assert s0.getvalue() == expected_result


@pytest.mark.parametrize(
    "value",
    (0, 1, 128, 2 ** 32, 2 ** 64 - 1),
)
@pytest.mark.asyncio
async def test_read_write_varint(value):
    s = io.BytesIO()
    write_varint(s, value)
    s.seek(0, 0)

    async def read_byte(s):
        data = s.read(1)
        return data[0]

    result = await read_varint(s, read_byte)
    assert value == result


def test_read_varint_overflow():
    pass
