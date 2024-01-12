from eth_utils import (
    big_endian_to_int,
    decode_hex,
    is_same_address,
)
import pytest

from eth._utils.address import (
    generate_safe_contract_address,
)


@pytest.mark.parametrize(
    # Test cases from: https://eips.ethereum.org/EIPS/eip-1014
    "origin, salt, code, expected",
    (
        (
            "0x0000000000000000000000000000000000000000",
            "0x0000000000000000000000000000000000000000000000000000000000000000",
            "0x00",
            "0x4D1A2e2bB4F88F0250f26Ffff098B0b30B26BF38",
        ),
        (
            "0xdeadbeef00000000000000000000000000000000",
            "0x0000000000000000000000000000000000000000",
            "0x00",
            "0xB928f69Bb1D91Cd65274e3c79d8986362984fDA3",
        ),
        (
            "0xdeadbeef00000000000000000000000000000000",
            "0x000000000000000000000000feed000000000000000000000000000000000000",
            "0x00",
            "0xD04116cDd17beBE565EB2422F2497E06cC1C9833",
        ),
        (
            "0x0000000000000000000000000000000000000000",
            "0x0000000000000000000000000000000000000000",
            "0xdeadbeef",
            "0x70f2b2914A2a4b783FaEFb75f459A580616Fcb5e",
        ),
        (
            "0x00000000000000000000000000000000deadbeef",
            "0x00000000000000000000000000000000000000000000000000000000cafebabe",
            "0xdeadbeef",
            "0x60f3f640a8508fC6a86d45DF051962668E1e8AC7",
        ),
        (
            "0x00000000000000000000000000000000deadbeef",
            "0x00000000000000000000000000000000000000000000000000000000cafebabe",
            "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",  # noqa: E501
            "0x1d8bfDC5D46DC4f61D6b6115972536eBE6A8854C",
        ),
        (
            "0x0000000000000000000000000000000000000000",
            "0x0000000000000000000000000000000000000000000000000000000000000000",
            "0x",
            "0xE33C0C7F7df4809055C3ebA6c09CFe4BaF1BD9e0",
        ),
    ),
)
def test_generate_safe_contract_address(origin, salt, code, expected):
    address = generate_safe_contract_address(
        decode_hex(origin), big_endian_to_int(decode_hex(salt)), decode_hex(code)
    )

    assert is_same_address(address, expected)
