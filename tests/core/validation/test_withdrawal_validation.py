from eth_typing import (
    Address,
)
from eth_utils import (
    ValidationError,
    to_hex,
)
import pytest

from eth.validation import (
    UINT_64_MAX,
)
from eth.vm.forks.shanghai.withdrawals import (
    Withdrawal,
)


@pytest.mark.parametrize(
    "withdrawal",
    (
        Withdrawal(0, 0, Address(b"\x00" * 20), 0),
        Withdrawal(1, 1, Address(b"\xff" * 20), 1),
        Withdrawal(
            1337,
            1337,
            Address(
                b"\x85\x82\xa2\x89V\xb9%\x93M\x03\xdd\xb4Xu\xe1\x8e\x85\x93\x12\xc1"
            ),
            1337,
        ),
        Withdrawal(UINT_64_MAX, UINT_64_MAX, Address(b"\x00" * 20), UINT_64_MAX),
    ),
)
def test_valid_withdrawal_fields(withdrawal):
    withdrawal.validate()


@pytest.mark.parametrize(
    "withdrawal,message",
    (
        # validate `index`, `validator_index`, and `amount` fields
        (Withdrawal(-1, 0, Address(b"\x00" * 20), 0), "cannot be negative"),
        (Withdrawal(0, -1, Address(b"\x00" * 20), 1), "cannot be negative"),
        (Withdrawal(0, 0, Address(b"\x00" * 20), -1), "cannot be negative"),
        (
            Withdrawal(
                UINT_64_MAX + 1,
                UINT_64_MAX,
                Address(b"\x00" * 20),
                UINT_64_MAX,
            ),
            "exceeds maximum uint64 size",
        ),
        (
            Withdrawal(
                UINT_64_MAX,
                UINT_64_MAX + 1,
                Address(b"\x00" * 20),
                UINT_64_MAX,
            ),
            "exceeds maximum uint64 size",
        ),
        (
            Withdrawal(
                UINT_64_MAX,
                UINT_64_MAX,
                Address(b"\x00" * 20),
                UINT_64_MAX + 1,
            ),
            "exceeds maximum uint64 size",
        ),
        # validate `address` field
        (Withdrawal(0, 0, Address(b"\x00" * 19), 0), "not a valid canonical address"),
        (Withdrawal(0, 0, Address(b"\x00" * 21), 0), "not a valid canonical address"),
        (Withdrawal(0, 0, Address(b"\x00"), 0), "not a valid canonical address"),
        (Withdrawal(0, 0, to_hex(b"\x00" * 20), 0), "not a valid canonical address"),
    ),
    ids=[
        "negative index",
        "negative validator_index",
        "negative amount",
        "index is UINT_64_MAX plus one",
        "validator_index is UINT_64_MAX plus one",
        "amount is UINT_64_MAX plus one",
        "address size is 19 bytes",
        "address size is 21 bytes",
        "address size is 1 byte",
        "address is valid but provided as hex string",
    ],
)
def test_invalid_withdrawal_fields(withdrawal, message):
    with pytest.raises(ValidationError, match=message):
        withdrawal.validate()
