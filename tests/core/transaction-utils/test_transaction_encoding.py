from eth_utils import (
    ValidationError,
    decode_hex,
    to_bytes,
    to_int,
)
import pytest
import rlp

from eth.exceptions import (
    UnrecognizedTransactionType,
)
from eth.vm.forks import (
    BerlinVM,
    LondonVM,
)

# Add recognized types here if any fork knows about it. Then,
#   add manual unrecognized types for older forks. For example,
#   (BerlinVM, to_bytes(2), UnrecognizedTransactionType) should be added explicitly.
RECOGNIZED_TRANSACTION_TYPES = {1, 2}

UNRECOGNIZED_TRANSACTION_TYPES = tuple(
    (to_bytes(val), UnrecognizedTransactionType)
    for val in range(0, 0x80)
    if val not in RECOGNIZED_TRANSACTION_TYPES
)

# These are valid RLP byte-strings, but invalid for EIP-2718
INVALID_TRANSACTION_TYPES = tuple(
    (rlp.encode(to_bytes(val)), ValidationError) for val in range(0x80, 0x100)
)


@pytest.mark.parametrize("vm_class", [BerlinVM, LondonVM])
@pytest.mark.parametrize(
    "encoded, expected",
    (
        (
            decode_hex(
                "0xdd80010294ffffffffffffffffffffffffffffffffffffffff0380040506"
            ),
            dict(
                nonce=0,
                gas_price=1,
                gas=2,
                to=b"\xff" * 20,
                value=3,
                data=b"",
                v=4,
                r=5,
                s=6,
            ),
        ),
        (
            decode_hex("0xc0"),
            rlp.exceptions.DeserializationError,
        ),
    )
    + UNRECOGNIZED_TRANSACTION_TYPES
    + INVALID_TRANSACTION_TYPES,
)
def test_transaction_decode(vm_class, encoded, expected):
    sedes = vm_class.get_transaction_builder()
    if type(expected) is type and issubclass(expected, Exception):
        with pytest.raises(expected):
            rlp.decode(encoded, sedes=sedes)
    else:
        # Check that the given transaction encodes to the start encoding
        expected_txn = sedes.new_transaction(**expected)
        expected_encoding = rlp.encode(expected_txn)
        assert encoded == expected_encoding

        # Check that the encoded bytes decode to the given data
        decoded = rlp.decode(encoded, sedes=sedes)
        assert decoded == expected_txn


@pytest.mark.parametrize(
    "vm_class, encoded, expected_failure",
    (
        (
            BerlinVM,
            to_bytes(2),
            UnrecognizedTransactionType,
        ),
    ),
)
def test_transaction_decode_failure_by_vm(vm_class, encoded, expected_failure):
    sedes = vm_class.get_transaction_builder()
    with pytest.raises(expected_failure):
        rlp.decode(encoded, sedes=sedes)


@pytest.mark.parametrize("is_rlp_encoded", (True, False))
def test_EIP2930_transaction_decode(typed_txn_fixture, is_rlp_encoded):
    signed_txn = decode_hex(typed_txn_fixture["signed"])
    transaction_builder = BerlinVM.get_transaction_builder()
    if is_rlp_encoded:
        rlp_encoded = rlp.encode(signed_txn)
        transaction = rlp.decode(rlp_encoded, sedes=transaction_builder)
    else:
        transaction = transaction_builder.decode(signed_txn)

    assert transaction.chain_id == typed_txn_fixture["chainId"]
    assert transaction.nonce == typed_txn_fixture["nonce"]
    assert transaction.gas_price == typed_txn_fixture["gasPrice"]
    assert transaction.gas == typed_txn_fixture["gas"]
    assert transaction.to == decode_hex(typed_txn_fixture["to"])
    assert transaction.value == typed_txn_fixture["value"]
    assert transaction.data == decode_hex(typed_txn_fixture["data"])
    assert len(transaction.access_list) == len(typed_txn_fixture["access_list"])
    access_test_data = zip(transaction.access_list, typed_txn_fixture["access_list"])
    for (account, slots), (expected_account, expected_slots) in access_test_data:
        assert account == expected_account
        assert slots == tuple(to_int(expected) for expected in expected_slots)


@pytest.mark.parametrize("is_rlp_encoded", (True, False))
def test_EIP2930_transaction_inferred_attributes(typed_txn_fixture, is_rlp_encoded):
    signed_txn = decode_hex(typed_txn_fixture["signed"])
    transaction_builder = BerlinVM.get_transaction_builder()
    if is_rlp_encoded:
        double_encoded = rlp.encode(signed_txn)
        transaction = rlp.decode(double_encoded, sedes=transaction_builder)
        assert rlp.encode(transaction) == double_encoded
        assert rlp.encode(transaction, cache=False) == double_encoded
    else:
        transaction = transaction_builder.decode(signed_txn)

    assert transaction.hash == decode_hex(typed_txn_fixture["hash"])
    assert transaction.intrinsic_gas == typed_txn_fixture["intrinsic_gas"]
    assert transaction.get_intrinsic_gas() == typed_txn_fixture["intrinsic_gas"]
