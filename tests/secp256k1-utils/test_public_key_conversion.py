import pytest

from evm.utils.secp256k1 import (
    private_key_to_public_key,
)


@pytest.mark.parametrize(
    'private_key,expected',
    (
        (
            b"\xe9\x87=y\xc6\xd8}\xc0\xfbjWxc3\x89\xf4E2\x130=\xa6\x1f \xbdg\xfc#:\xa32b",
            b"\x04X\x8d *\xfc\xc1\xeeJ\xb5%LxG\xec%\xb9\xa15\xbb\xda\x0f+\xc6\x9e\xe1\xa7\x14t\x9f\xd7}\xc9\xf8\x8f\xf2\xa0\r~u-D\xcb\xe1n\x1e\xbc\xf0\x89\x0bv\xec|x\x88a\t\xde\xe7l\xcf\xc8DT$",
        ),
    ),
)
def test_private_key_to_public_key(private_key, expected):
    actual = private_key_to_public_key(private_key)
    assert actual == expected
