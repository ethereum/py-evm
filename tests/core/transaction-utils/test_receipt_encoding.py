from eth_utils import (
    ValidationError,
    decode_hex,
    to_bytes,
)
import pytest
import rlp

from eth.exceptions import (
    UnrecognizedTransactionType,
)
from eth.rlp.receipts import (
    Receipt,
)
from eth.vm.forks import (
    BerlinVM,
    LondonVM,
)
from eth.vm.forks.berlin.receipts import (
    TypedReceipt,
)

# The type of receipt is based on the type of the transaction. So we are
#   checking the type of the receipt against known transaction types.
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
                "f90185a01e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e01b9010000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002f85ef85c942d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2df842a00000000000000000000000000000000000000000000000000000000000000003a00000000000000000000000000000000000000000000000000000000000000004829999"  # noqa: E501
            ),
            Receipt(
                state_root=b"\x1e" * 32,
                gas_used=1,
                bloom=2,
                logs=[
                    [b"\x2d" * 20, [3, 4], b"\x99" * 2],
                ],
            ),
        ),
        (
            decode_hex(
                "01f90185a01e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e01b9010000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002f85ef85c942d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2d2df842a00000000000000000000000000000000000000000000000000000000000000003a00000000000000000000000000000000000000000000000000000000000000004829999"  # noqa: E501
            ),
            TypedReceipt(
                type_id=1,
                proxy_target=Receipt(
                    state_root=b"\x1e" * 32,
                    gas_used=1,
                    bloom=2,
                    logs=[
                        [b"\x2d" * 20, [3, 4], b"\x99" * 2],
                    ],
                ),
            ),
        ),
    ),
)
def test_receipt_decode(vm_class, encoded, expected):
    expected_encoding = expected.encode()
    assert encoded == expected_encoding

    sedes = vm_class.get_receipt_builder()
    decoded = sedes.decode(encoded)
    assert decoded == expected


@pytest.mark.parametrize("vm_class", [BerlinVM, LondonVM])
@pytest.mark.parametrize(
    "encoded, expected_failure",
    (
        (
            decode_hex("0xc0"),
            rlp.exceptions.DeserializationError,
        ),
    )
    + UNRECOGNIZED_TRANSACTION_TYPES
    + INVALID_TRANSACTION_TYPES,
)
def test_receipt_decode_failure(vm_class, encoded, expected_failure):
    sedes = vm_class.get_receipt_builder()
    with pytest.raises(expected_failure):
        rlp.decode(encoded, sedes=sedes)


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
def test_receipt_decode_failure_by_vm(vm_class, encoded, expected_failure):
    sedes = vm_class.get_receipt_builder()
    with pytest.raises(expected_failure):
        rlp.decode(encoded, sedes=sedes)


@pytest.mark.parametrize("is_legacy", (True, False))
@pytest.mark.parametrize("is_rlp_encoded", (True, False))
def test_EIP2930_receipt_decode(is_legacy, is_rlp_encoded):
    expected_vals = dict(
        state_root=b"\xee",
        gas_used=1,
        bloom=2,
        logs=[
            dict(address=b"\x0f" * 20, topics=(3, 4), data=b"\xaa"),
        ],
    )
    legacy_encoded = b"\xf9\x01e\x81\xee\x01\xb9\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\xf8]\xf8[\x94\x0f\x0f\x0f\x0f\x0f\x0f\x0f\x0f\x0f\x0f\x0f\x0f\x0f\x0f\x0f\x0f\x0f\x0f\x0f\x0f\xf8B\xa0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\xa0\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x04\x81\xaa"  # noqa: E501
    if is_legacy:
        encoded = legacy_encoded
        if is_rlp_encoded:
            pytest.skip("No examples where legacy receipts are double-encoded")
    else:
        encoded = b"\x01" + legacy_encoded

    receipt_builder = BerlinVM.get_receipt_builder()
    if is_rlp_encoded:
        double_encoded = rlp.encode(encoded)
        receipt = rlp.decode(double_encoded, sedes=receipt_builder)
        assert rlp.encode(receipt) == double_encoded
        assert rlp.encode(receipt, cache=False) == double_encoded
    else:
        receipt = receipt_builder.decode(encoded)

        re_encoded = receipt.encode()
        assert encoded == re_encoded

    assert receipt.state_root == expected_vals["state_root"]
    assert receipt.gas_used == expected_vals["gas_used"]
    assert receipt.bloom == expected_vals["bloom"]

    expected_logs = expected_vals["logs"]
    assert len(receipt.logs) == len(expected_logs)
    for log, expected_log in zip(receipt.logs, expected_logs):
        assert log.address == expected_log["address"]
        assert log.topics == expected_log["topics"]
        assert log.data == expected_log["data"]
