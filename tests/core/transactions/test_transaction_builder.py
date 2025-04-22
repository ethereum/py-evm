import pytest

from eth_keys.datatypes import (
    PrivateKey,
)

from eth.vm.forks.prague.transactions import (
    Authorization,
    PragueTransactionBuilder,
)

AUTH1 = {
    "chain_id": 1,
    "address": b"\x00" * 20,
    "nonce": 2,
    "y_parity": 0,
    "r": 0,
    "s": 0,
}
AUTH2 = {
    "chain_id": 0,
    "address": b"\x00" * 19 + b"\x01",
    "nonce": 2**64 - 1,
    "y_parity": 2**8 - 1,
    "r": 2**256 - 1,
    "s": 2**256 - 1,
}


# test both auth dicts and Authorization instances
@pytest.mark.parametrize(
    "authorization_list",
    (
        [AUTH1, AUTH2],
        [Authorization(**AUTH1), Authorization(**AUTH2)],
    ),
)
def test_prague_transaction_builder_set_code_transaction(authorization_list):
    builder = PragueTransactionBuilder()

    unsigned = builder.new_unsigned_set_code_transaction(
        **{
            "chain_id": 1,
            "nonce": 1,
            "max_priority_fee_per_gas": 1,
            "max_fee_per_gas": 1,
            "gas": 1,
            "to": b"\x00" * 20,
            "value": 1,
            "data": b"\x00" * 32 + b"\x01",
            "access_list": [(b"\x00" * 20, [0])],
            "authorization_list": authorization_list,
        }
    )

    key = PrivateKey(b"\x01" * 32)
    unsigned.as_signed_transaction(
        private_key=key,
        chain_id=1,
    )
