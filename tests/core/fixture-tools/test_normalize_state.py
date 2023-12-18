from eth_utils import (
    ValidationError,
    big_endian_to_int,
)
import pytest

from eth.tools._utils.normalization import (
    normalize_state,
)

ADDRESS_A = b"a" + b"\0" * 19
ADDRESS_B = b"b" + b"\0" * 19


@pytest.mark.parametrize(
    "value,expected",
    (
        # as state dictionaries
        (
            ({ADDRESS_A: {"balance": 1}},),
            {ADDRESS_A: {"balance": 1}},
        ),
        (
            ({ADDRESS_A: {"balance": 1}, ADDRESS_B: {"balance": 2}},),
            {ADDRESS_A: {"balance": 1}, ADDRESS_B: {"balance": 2}},
        ),
        # as shorthand tuples
        (
            ((ADDRESS_A, "balance", 1),),
            {ADDRESS_A: {"balance": 1}},
        ),
        (
            (
                (ADDRESS_A, "balance", 1),
                (ADDRESS_B, "balance", 2),
            ),
            {ADDRESS_A: {"balance": 1}, ADDRESS_B: {"balance": 2}},
        ),
        (
            (
                (ADDRESS_A, "balance", 1),
                (ADDRESS_A, "nonce", 1),
            ),
            {ADDRESS_A: {"balance": 1, "nonce": 1}},
        ),
        (
            (
                (ADDRESS_A, "balance", 1),
                (ADDRESS_A, "storage", 1, b"arst"),
            ),
            {ADDRESS_A: {"balance": 1, "storage": {1: big_endian_to_int(b"arst")}}},
        ),
        (
            (
                (ADDRESS_A, "balance", 1),
                (ADDRESS_A, "storage", 1, 12345),
            ),
            {ADDRESS_A: {"balance": 1, "storage": {1: 12345}}},
        ),
        (
            (
                (ADDRESS_A, "balance", 1),
                (ADDRESS_A, "storage", 1, 12345),
                (ADDRESS_A, "storage", 2, 54321),
            ),
            {ADDRESS_A: {"balance": 1, "storage": {1: 12345, 2: 54321}}},
        ),
        # mixed dicts and shorthand
        (
            ({ADDRESS_A: {"balance": 1}}, (ADDRESS_B, "balance", 2)),
            {ADDRESS_A: {"balance": 1}, ADDRESS_B: {"balance": 2}},
        ),
    ),
)
def test_normalize_state(value, expected):
    actual = normalize_state(value)
    assert actual == expected


@pytest.mark.parametrize(
    "value",
    (
        (
            (ADDRESS_A, "balance", 1),
            (ADDRESS_A, "balance", 2),
        ),
        (
            (ADDRESS_A, "storage", 1, 12345),
            (ADDRESS_A, "storage", 1, 54321),
        ),
    ),
)
def test_normalize_state_detects_duplicates(value):
    with pytest.raises(
        ValidationError, match="Some state item is defined multiple times"
    ):
        normalize_state(value)


def test_normalize_state_detects_bad_keys():
    with pytest.raises(ValidationError, match="not-a-key"):
        normalize_state(((ADDRESS_A, "not-a-key", 3),))
