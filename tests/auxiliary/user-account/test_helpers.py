import pytest

from eth_keys import keys

from cytoolz import (
    merge,
)

from evm.exceptions import ValidationError

from evm.auxiliary.user_account_contract.transaction import (
    UserAccountTransaction,
    UnsignedUserAccountTransaction
)

VALID_PARAMS = {
    "chain_id": 1,
    "shard_id": 2,
    "to": b"\xaa" * 20,
    "gas": 300000,
    "access_list": [[b"\xaa" * 20, b"\x00"]],
    "destination": b"\xbb" * 20,
    "value": 4,
    "nonce": 5,
    "min_block": 6,
    "max_block": 7,
    "gas_price": 8,
    "msg_data": b"\xcc" * 123,
}

INVALID_PARAMS = {
    "chain_id": b"\x01",
    "shard_id": b"\x02",
    "to": "0x" + "aa" * 20,
    "gas": b"\x03",
    "access_list": [[b"\xaa" * 20, 0]],
    "destination": "0x" + "bb" * 20,
    "value": b"\x04",
    "nonce": b"\x05",
    "min_block": b"\x06",
    "max_block": b"\x07",
    "gas_price": b"\x08",
    "msg_data": 123,
}


@pytest.fixture
def unsigned_transaction():
    return UnsignedUserAccountTransaction(**VALID_PARAMS)


def test_signing(unsigned_transaction):
    private_key = keys.PrivateKey(b"\x22" * 32)
    signed_transaction = unsigned_transaction.as_signed_transaction(private_key)
    assert signed_transaction.get_sender() == private_key.public_key.to_canonical_address()


def test_data(unsigned_transaction):
    private_key = keys.PrivateKey(b"\x22" * 32)
    signed_transaction = unsigned_transaction.as_signed_transaction(private_key)
    assert len(signed_transaction.data) > 10 * 32
    assert signed_transaction.data.endswith(signed_transaction.msg_data)
    assert signed_transaction.data.endswith(unsigned_transaction.msg_data)
    assert len(signed_transaction.data) == len(unsigned_transaction.data) + 96


@pytest.mark.parametrize("key,value", INVALID_PARAMS.items())
def test_validation(key, value):
    # construct object with valid parameters, apply invalid values afterwards
    # this ensures object creation succeeds
    tx = UnsignedUserAccountTransaction(**VALID_PARAMS)
    with pytest.raises(ValidationError):
        setattr(tx, key, value)
        tx.validate()

    tx = UserAccountTransaction(**merge(VALID_PARAMS, {"v": 27, "r": 1, "s": 1}))
    with pytest.raises(ValidationError):
        setattr(tx, key, value)
        tx.validate()
