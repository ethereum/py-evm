from eth_utils import (
    ValidationError,
)
import pytest

from eth.vm.forks.berlin.transactions import (
    UnsignedAccessListTransaction,
)
from eth.vm.forks.london.transactions import (
    UnsignedDynamicFeeTransaction,
)


@pytest.mark.parametrize(
    "unsigned_access_list_transaction,is_valid",
    (
        # While ethereum tests do not yet have Berlin or London transaction tests,
        # this adds a few tests to test some obvious cases,
        # especially positive test cases.
        (
            UnsignedAccessListTransaction(
                chain_id=123456789,
                nonce=0,
                gas_price=1000000000,
                gas=40000,
                to=b"\xf0" * 20,
                value=0,
                data=b"",
                access_list=((b"\xf0" * 20, (1, 2)),),
            ),
            True,
        ),
        (
            UnsignedAccessListTransaction(
                chain_id=0,
                nonce=0,
                gas_price=0,
                gas=0,
                to=b"\xf0" * 20,
                value=0,
                data=b"",
                access_list=(),
            ),
            True,
        ),
        (
            UnsignedAccessListTransaction(
                chain_id=123456789,
                nonce=0,
                gas_price=1000000000,
                gas=40000,
                to=b"\xf0" * 20,
                value=0,
                data=b"",
                access_list=((b"\xf0" * 20, ()),),
            ),
            True,
        ),
        (
            UnsignedAccessListTransaction(
                chain_id=123456789,
                nonce=0,
                gas_price=1000000000,
                gas=40000,
                to=b"\xf0" * 20,
                value=0,
                data=b"",
                access_list=(
                    (b"\xf0" * 19, (1,)),
                ),  # access_list address fails validation
            ),
            False,
        ),
        (
            UnsignedAccessListTransaction(
                chain_id="1",  # chain_id fails validation
                nonce=0,
                gas_price=0,
                gas=0,
                to=b"\xf0" * 20,
                value=0,
                data=b"",
                access_list=(),
            ),
            False,
        ),
    ),
)
def test_validate_unsigned_access_list_transaction(
    unsigned_access_list_transaction, is_valid
):
    if is_valid:
        unsigned_access_list_transaction.validate()
    else:
        with pytest.raises(ValidationError):
            unsigned_access_list_transaction.validate()


@pytest.mark.parametrize(
    "unsigned_dynamic_fee_transaction,is_valid",
    (
        # While ethereum tests do not yet have Berlin or London transaction tests,
        # this adds a few tests to test some obvious cases,
        # especially positive test cases.
        (
            UnsignedDynamicFeeTransaction(
                chain_id=123456789,
                nonce=0,
                max_fee_per_gas=1000000000,
                max_priority_fee_per_gas=1000000000,
                gas=40000,
                to=b"\xf0" * 20,
                value=0,
                data=b"",
                access_list=((b"\xf0" * 20, (1, 2)),),
            ),
            True,
        ),
        (
            UnsignedDynamicFeeTransaction(
                chain_id=0,
                nonce=0,
                max_fee_per_gas=0,
                max_priority_fee_per_gas=0,
                gas=0,
                to=b"\xf0" * 20,
                value=0,
                data=b"",
                access_list=(),
            ),
            True,
        ),
        (
            UnsignedDynamicFeeTransaction(
                chain_id=123456789,
                nonce=0,
                max_fee_per_gas=1000000000,
                max_priority_fee_per_gas=1000000000,
                gas=40000,
                to=b"\xf0" * 20,
                value=0,
                data=b"",
                access_list=((b"\xf0" * 20, ()),),
            ),
            True,
        ),
        (
            UnsignedDynamicFeeTransaction(
                chain_id=123456789,
                nonce=0,
                max_fee_per_gas=1000000000,
                max_priority_fee_per_gas=1000000000,
                gas=40000,
                to=b"\xf0" * 20,
                value=0,
                data=b"",
                access_list=(
                    (b"\xf0" * 19, (1,)),
                ),  # access_list address fails validation
            ),
            False,
        ),
        (
            UnsignedDynamicFeeTransaction(
                chain_id="1",  # chain_id fails validation
                nonce=0,
                max_fee_per_gas=1000000000,
                max_priority_fee_per_gas=1000000000,
                gas=0,
                to=b"\xf0" * 20,
                value=0,
                data=b"",
                access_list=(),
            ),
            False,
        ),
    ),
)
def test_validate_unsigned_dynamic_fee_transaction(
    unsigned_dynamic_fee_transaction, is_valid
):
    if is_valid:
        unsigned_dynamic_fee_transaction.validate()
    else:
        with pytest.raises(ValidationError):
            unsigned_dynamic_fee_transaction.validate()
