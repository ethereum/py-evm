import pytest

import rlp

from eth_utils import (
    decode_hex,
    is_same_address,
)

from eth_keys import keys

from evm.vm.forks.frontier.transactions import (
    FrontierTransaction,
)
from evm.vm.forks.homestead.transactions import (
    HomesteadTransaction,
)

from evm.utils.transactions import (
    extract_transaction_sender,
    validate_transaction_signature,
)


@pytest.mark.parametrize(
    "txn_class",
    (FrontierTransaction, HomesteadTransaction),
)
def test_pre_EIP155_transaction_signature_validation(txn_class, txn_fixture):
    if txn_fixture['chainId'] is not None:
        pytest.skip("Only testng non-EIP155 transactions")
    transaction = rlp.decode(decode_hex(txn_fixture['signed']), sedes=txn_class)
    validate_transaction_signature(transaction)
    transaction.check_signature_validity()


@pytest.mark.parametrize(
    "txn_class",
    (FrontierTransaction, HomesteadTransaction),
)
def test_pre_EIP155_transaction_sender_extraction(txn_class, txn_fixture):
    if txn_fixture['chainId'] is not None:
        pytest.skip("Only testng non-EIP155 transactions")
    key = keys.PrivateKey(decode_hex(txn_fixture['key']))
    transaction = rlp.decode(decode_hex(txn_fixture['signed']), sedes=txn_class)
    sender = extract_transaction_sender(transaction)
    assert is_same_address(sender, key.public_key.to_canonical_address())
