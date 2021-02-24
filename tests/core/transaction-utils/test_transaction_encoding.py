from eth_utils import (
    decode_hex,
    to_bytes,
)
import pytest
import rlp

from eth.exceptions import UnrecognizedTransactionType
from eth.vm.forks import (
    BerlinVM,
)

UNRECOGNIZED_TRANSACTION_TYPES = tuple(
    (to_bytes(val), UnrecognizedTransactionType)
    for val in range(0, 0x80)
)

# These are valid RLP byte-strings, but invalid for EIP-2718
INVALID_TRANSACTION_TYPES = tuple(
    (rlp.encode(to_bytes(val)), rlp.exceptions.DeserializationError)
    for val in range(0x80, 0x100)
)


@pytest.mark.parametrize('vm_class', [BerlinVM])
@pytest.mark.parametrize(
    'encoded, expected',
    (
        (
            decode_hex('0xdd80010294ffffffffffffffffffffffffffffffffffffffff0380040506'),
            dict(
                nonce=0,
                gas_price=1,
                gas=2,
                to=b'\xff' * 20,
                value=3,
                data=b'',
                v=4,
                r=5,
                s=6,
            ),
        ),
        (
            decode_hex('0xc0'),
            rlp.exceptions.DeserializationError,
        ),
    )
    + UNRECOGNIZED_TRANSACTION_TYPES
    + INVALID_TRANSACTION_TYPES
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
