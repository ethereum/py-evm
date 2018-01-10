import pytest

from eth_keys import keys

from evm.auxiliary.user_account_contract.transaction import (
    ForwardingTransaction,
)


@pytest.fixture
def unsigned_transaction():
    return ForwardingTransaction(
        chain_id=1,
        shard_id=2,
        to=b"\xaa" * 20,
        gas=3,
        access_list=[[b"\xaa" * 20, b"\x00"]],
        destination=b"\xbb" * 20,
        value=4,
        nonce=5,
        min_block=6,
        max_block=7,
        gas_price=8,
        msg_data=b"\xcc" * 123,
    )


def test_forwarding_transaction(unsigned_transaction):
    # test initialization
    assert unsigned_transaction.chain_id == 1
    assert unsigned_transaction.shard_id == 2
    assert unsigned_transaction.to == b"\xaa" * 20
    assert unsigned_transaction.gas == 3
    assert unsigned_transaction.access_list == [[b"\xaa" * 20, b"\x00"]]
    assert unsigned_transaction.destination == b"\xbb" * 20
    assert unsigned_transaction.value == 4
    assert unsigned_transaction.nonce == 5
    assert unsigned_transaction.min_block == 6
    assert unsigned_transaction.max_block == 7
    assert unsigned_transaction.int_gas_price == 8
    assert unsigned_transaction.msg_data == b"\xcc" * 123
    assert unsigned_transaction.vrs == (0, 0, 0)

    # test getters and setters
    unsigned_transaction.chain_id = 2
    assert unsigned_transaction.chain_id == 2

    unsigned_transaction.shard_id = 3
    assert unsigned_transaction.shard_id == 3

    unsigned_transaction.to = b"\xbb" * 20
    assert unsigned_transaction.to == b"\xbb" * 20

    unsigned_transaction.gas = 4
    assert unsigned_transaction.gas == 4

    unsigned_transaction.access_list = []
    assert unsigned_transaction.access_list == []

    unsigned_transaction.destination = b"\xcc" * 20
    assert unsigned_transaction.destination == b"\xcc" * 20

    unsigned_transaction.value = 5
    assert unsigned_transaction.value == 5

    unsigned_transaction.nonce = 6
    assert unsigned_transaction.nonce == 6

    unsigned_transaction.min_block = 7
    assert unsigned_transaction.min_block == 7

    unsigned_transaction.max_block = 8
    assert unsigned_transaction.max_block == 8

    unsigned_transaction.int_gas_price = 9
    assert unsigned_transaction.int_gas_price == 9

    unsigned_transaction.msg_data = b"\xdd" * 99
    assert unsigned_transaction.msg_data == b"\xdd" * 99

    unsigned_transaction.vrs = (1, 2, 3)
    assert unsigned_transaction.vrs == (1, 2, 3)


def test_signing(unsigned_transaction):
    assert not unsigned_transaction.is_signed
    private_key = keys.PrivateKey(b"\x22" * 32)
    unsigned_transaction.sign(private_key)
    assert unsigned_transaction.is_signed
    assert unsigned_transaction.get_sender() == private_key.public_key.to_canonical_address()
