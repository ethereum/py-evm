import pytest

import rlp

from eth_utils import (
    decode_hex,
    is_same_address,
    to_canonical_address,
)

from eth_keys import keys

from eth.vm.forks.frontier.transactions import (
    FrontierTransaction,
)
from eth.vm.forks.homestead.transactions import (
    HomesteadTransaction,
)
from eth.vm.forks.spurious_dragon.transactions import (
    SpuriousDragonTransaction,
)

from eth._utils.transactions import (
    extract_transaction_sender,
    validate_transaction_signature,
)


@pytest.fixture(params=[FrontierTransaction, HomesteadTransaction, SpuriousDragonTransaction])
def transaction_class(request):
    return request.param


def test_pre_EIP155_transaction_signature_validation(transaction_class, txn_fixture):
    if txn_fixture['chainId'] is not None:
        pytest.skip("Only testng non-EIP155 transactions")
    transaction = rlp.decode(decode_hex(txn_fixture['signed']), sedes=transaction_class)
    validate_transaction_signature(transaction)
    transaction.check_signature_validity()


def test_EIP155_transaction_signature_validation(txn_fixture):
    transaction = rlp.decode(decode_hex(txn_fixture['signed']), sedes=SpuriousDragonTransaction)
    validate_transaction_signature(transaction)
    transaction.check_signature_validity()


def test_pre_EIP155_transaction_sender_extraction(transaction_class, txn_fixture):
    if txn_fixture['chainId'] is not None:
        pytest.skip("Only testng non-EIP155 transactions")
    key = keys.PrivateKey(decode_hex(txn_fixture['key']))
    transaction = rlp.decode(decode_hex(txn_fixture['signed']), sedes=transaction_class)
    sender = extract_transaction_sender(transaction)

    assert is_same_address(sender, transaction.sender)
    assert is_same_address(sender, key.public_key.to_canonical_address())


def test_EIP155_transaction_sender_extraction(txn_fixture):
    key = keys.PrivateKey(decode_hex(txn_fixture['key']))
    transaction = rlp.decode(decode_hex(txn_fixture['signed']), sedes=SpuriousDragonTransaction)
    sender = extract_transaction_sender(transaction)
    assert is_same_address(sender, transaction.sender)
    assert is_same_address(sender, key.public_key.to_canonical_address())


def test_unsigned_to_signed_transaction(txn_fixture, transaction_class):
    key = keys.PrivateKey(decode_hex(txn_fixture['key']))
    unsigned_txn = transaction_class.create_unsigned_transaction(
        nonce=txn_fixture['nonce'],
        gas_price=txn_fixture['gasPrice'],
        gas=txn_fixture['gas'],
        to=(
            to_canonical_address(txn_fixture['to'])
            if txn_fixture['to']
            else b''
        ),
        value=txn_fixture['value'],
        data=decode_hex(txn_fixture['data']),
    )
    signed_txn = unsigned_txn.as_signed_transaction(key)

    assert is_same_address(signed_txn.sender, key.public_key.to_canonical_address())


def test_unsigned_to_eip155_signed_transaction(txn_fixture, transaction_class):
    if txn_fixture['chainId'] is None:
        pytest.skip('No chain id for EIP155 signing')
    elif not hasattr(transaction_class, 'chain_id'):
        pytest.skip('Transaction class is not chain aware')

    key = keys.PrivateKey(decode_hex(txn_fixture['key']))
    unsigned_txn = transaction_class.create_unsigned_transaction(
        nonce=txn_fixture['nonce'],
        gas_price=txn_fixture['gasPrice'],
        gas=txn_fixture['gas'],
        to=(
            to_canonical_address(txn_fixture['to'])
            if txn_fixture['to']
            else b''
        ),
        value=txn_fixture['value'],
        data=decode_hex(txn_fixture['data']),
    )
    signed_txn = unsigned_txn.as_signed_transaction(key, chain_id=txn_fixture['chainId'])

    assert is_same_address(signed_txn.sender, key.public_key.to_canonical_address())
    assert signed_txn.chain_id == txn_fixture['chainId']
