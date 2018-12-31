import pytest

from eth_typing import Hash32
from eth._utils.numeric import bitwise_xor

@pytest.mark.parametrize(
    'a,b,result',
    [
        (b'\x00' * 32, b'\x0a' * 32, b'\x0a' * 32),
    ]
)
def test_bitwise_xor_success(a, b, result):
    assert bitwise_xor(a, b) == result


@pytest.mark.parametrize(
    'a,b',
    [
        (b'\x00', b'\x0a' * 32),
        (b'\x00' * 32, b'\x0a'),
    ]
)
def test_bitwise_xor_failure(a, b):
    with pytest.raises(ValueError):
        bitwise_xor(a, b)
