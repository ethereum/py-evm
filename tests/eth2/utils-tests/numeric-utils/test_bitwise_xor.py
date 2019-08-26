import pytest

from eth2._utils.numeric import bitwise_xor


@pytest.mark.parametrize("a,b,result", [(b"\x00" * 32, b"\x0a" * 32, b"\x0a" * 32)])
def test_bitwise_xor_success(a, b, result):
    assert bitwise_xor(a, b) == result
