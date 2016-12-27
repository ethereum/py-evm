from __future__ import unicode_literals

import itertools

import pytest

from evm.utils.address import (
    is_address,
    is_hex_address,
    is_binary_address,
    is_32byte_address,
    is_normalized_address,
    is_canonical_address,
    normalize_address,
    canonicalize_address,
    is_same_address,
)


NORMAL_REPRESENTATION = "0xc6d9d2cd449a754c494264e1809c50e34d64562b"


CANONICAL_REPRESENTATION = b"\xc6\xd9\xd2\xcdD\x9auLIBd\xe1\x80\x9cP\xe3MdV+"


HEX_WITHOUT_NORMALIZED = (
    # Prefixed and unprefixed hex
    "c6d9d2cd449a754c494264e1809c50e34d64562b",
    b"0xc6d9d2cd449a754c494264e1809c50e34d64562b",
    b"c6d9d2cd449a754c494264e1809c50e34d64562b",
    # Checksummed
    "0xc6d9d2cD449A754c494264e1809c50e34D64562b",
    # Uppercased
    "0xC6D9D2CD449A754C494264E1809C50E34D64562B",
    "C6D9D2CD449A754C494264E1809C50E34D64562B",
)


HEX_REPRESENTATIONS = (NORMAL_REPRESENTATION,) + HEX_WITHOUT_NORMALIZED


BINARY_WITHOUT_CANONICAL = (
    "\xc6\xd9\xd2\xcdD\x9auLIBd\xe1\x80\x9cP\xe3MdV+",
)


BINARY_REPRESENTATIONS = (
    CANONICAL_REPRESENTATION,
) + BINARY_WITHOUT_CANONICAL


BYTES32_REPRESENTATIONS = (
    # 32 Byte Values
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc6\xd9\xd2\xcdD\x9auLIBd\xe1\x80\x9cP\xe3MdV+",
    "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc6\xd9\xd2\xcdD\x9auLIBd\xe1\x80\x9cP\xe3MdV+",
    "0x000000000000000000000000c6d9d2cd449a754c494264e1809c50e34d64562b",
    "000000000000000000000000c6d9d2cd449a754c494264e1809c50e34d64562b",
    b"0000000000000000000000000xc6d9d2cd449a754c494264e1809c50e34d64562b",
    b"000000000000000000000000c6d9d2cd449a754c494264e1809c50e34d64562b",
)


ADDRESS_REPRESENTATIONS = HEX_REPRESENTATIONS + BINARY_REPRESENTATIONS + BYTES32_REPRESENTATIONS


@pytest.mark.parametrize(
    "value,expected",
    (
        # Weird types
        (lambda : None, False),
        ("function", False),
        ({}, False),
        (True, False),
        (1, False),
    ) + tuple(
        zip(HEX_REPRESENTATIONS, itertools.repeat(True))
    ) + tuple(
        zip(BINARY_REPRESENTATIONS, itertools.repeat(True))
    ) + tuple(
        zip(BYTES32_REPRESENTATIONS, itertools.repeat(True))
    )
)
def test_is_address(value, expected):
    assert is_address(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    (
        # Weird types
        (lambda : None, False),
        ("function", False),
        ({}, False),
        (True, False),
        (1, False),
    ) + tuple(
        zip(HEX_REPRESENTATIONS, itertools.repeat(True))
    ) + tuple(
        zip(BINARY_REPRESENTATIONS, itertools.repeat(False))
    ) + tuple(
        zip(BYTES32_REPRESENTATIONS, itertools.repeat(False))
    )
)
def test_is_hex_address(value, expected):
    assert is_hex_address(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    (
        # Weird types
        (lambda : None, False),
        ("function", False),
        ({}, False),
        (True, False),
        (1, False),
    ) + tuple(
        zip(HEX_REPRESENTATIONS, itertools.repeat(False))
    ) + tuple(
        zip(BINARY_REPRESENTATIONS, itertools.repeat(True))
    ) + tuple(
        zip(BYTES32_REPRESENTATIONS, itertools.repeat(False))
    )
)
def test_is_binary_address(value, expected):
    assert is_binary_address(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    (
        # Weird types
        (lambda : None, False),
        ("function", False),
        ({}, False),
        (True, False),
        (1, False),
    ) + tuple(
        zip(HEX_REPRESENTATIONS, itertools.repeat(False))
    ) + tuple(
        zip(BINARY_REPRESENTATIONS, itertools.repeat(False))
    ) + tuple(
        zip(BYTES32_REPRESENTATIONS, itertools.repeat(True))
    )
)
def test_is_32byte_address(value, expected):
    assert is_32byte_address(value) == expected


@pytest.mark.parametrize(
    "value",
    ADDRESS_REPRESENTATIONS,
)
def test_normalize_address(value):
    assert normalize_address(value) == '0xc6d9d2cd449a754c494264e1809c50e34d64562b'


@pytest.mark.parametrize(
    "value,expected",
    tuple(
        zip(HEX_WITHOUT_NORMALIZED, itertools.repeat(False))
    ) + tuple(
        zip(BINARY_REPRESENTATIONS, itertools.repeat(False))
    ) + tuple(
        zip(BYTES32_REPRESENTATIONS, itertools.repeat(False))
    ) + (
        (NORMAL_REPRESENTATION, True),
    )
)
def test_is_normalized_address(value, expected):
    assert is_normalized_address(value) is expected


@pytest.mark.parametrize(
    "value",
    ADDRESS_REPRESENTATIONS,
)
def test_canonicalize_address(value):
    assert canonicalize_address(value) == b"\xc6\xd9\xd2\xcdD\x9auLIBd\xe1\x80\x9cP\xe3MdV+"


@pytest.mark.parametrize(
    "value,expected",
    tuple(
        zip(HEX_REPRESENTATIONS, itertools.repeat(False))
    ) + tuple(
        zip(BINARY_WITHOUT_CANONICAL, itertools.repeat(False))
    ) + tuple(
        zip(BYTES32_REPRESENTATIONS, itertools.repeat(False))
    ) + (
        (CANONICAL_REPRESENTATION, True),
    )
)
def test_is_canonical_address(value, expected):
    assert is_canonical_address(value) is expected


ADDRESS_REPRESENTATIONS = (
    # Prefixed and unprefixed hex
    "0xc6d9d2cd449a754c494264e1809c50e34d64562b",
    "c6d9d2cd449a754c494264e1809c50e34d64562b",
    b"0xc6d9d2cd449a754c494264e1809c50e34d64562b",
    b"c6d9d2cd449a754c494264e1809c50e34d64562b",
    # Checksummed
    "0xc6d9d2cD449A754c494264e1809c50e34D64562b",
    # Uppercased
    "0xC6D9D2CD449A754C494264E1809C50E34D64562B",
    "C6D9D2CD449A754C494264E1809C50E34D64562B",
    # Binary Values
    b"\xc6\xd9\xd2\xcdD\x9auLIBd\xe1\x80\x9cP\xe3MdV+",
    "\xc6\xd9\xd2\xcdD\x9auLIBd\xe1\x80\x9cP\xe3MdV+",
    # 32 Byte Values
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc6\xd9\xd2\xcdD\x9auLIBd\xe1\x80\x9cP\xe3MdV+",
    "\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc6\xd9\xd2\xcdD\x9auLIBd\xe1\x80\x9cP\xe3MdV+",
    "0x000000000000000000000000c6d9d2cd449a754c494264e1809c50e34d64562b",
    "000000000000000000000000c6d9d2cd449a754c494264e1809c50e34d64562b",
    b"0000000000000000000000000xc6d9d2cd449a754c494264e1809c50e34d64562b",
    b"000000000000000000000000c6d9d2cd449a754c494264e1809c50e34d64562b",
)


@pytest.mark.parametrize(
    "address1,address2",
    tuple(itertools.combinations_with_replacement(ADDRESS_REPRESENTATIONS, 2))
)
def test_is_same_address(address1, address2):
    assert is_same_address(address1, address2)
