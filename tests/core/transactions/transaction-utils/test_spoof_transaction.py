from eth_typing import (
    Address,
)
from toolz import (
    merge,
)

from eth.constants import (
    DEFAULT_SPOOF_R,
    DEFAULT_SPOOF_S,
    DEFAULT_SPOOF_Y_PARITY,
)
from eth.vm.forks import (
    LATEST_VM,
)
from eth.vm.spoof import (
    SpoofTransaction,
)


def test_spoof_transaction_with_from_spoofs_a_signed_transaction_with_default_fields():
    latest_txn_builder = LATEST_VM.get_transaction_builder()

    legacy_tx_values = {
        "nonce": 1,
        "gas_price": 1,
        "gas": 1,
        "to": Address(b"\x00" * 20),
        "value": 1,
        "data": b"",
    }

    access_list_tx_values = merge(
        legacy_tx_values,
        {
            "chain_id": 1,
            "access_list": [],
        },
    )

    dynamic_tx_values = merge(
        access_list_tx_values,
        {
            "max_priority_fee_per_gas": 1,
            "max_fee_per_gas": 1,
        },
    )
    dynamic_tx_values.pop("gas_price")
    blob_tx_values = merge(
        dynamic_tx_values,
        {
            "max_fee_per_blob_gas": 1,
            "blob_versioned_hashes": [],
        },
    )

    unsigned_legacy = latest_txn_builder.create_unsigned_transaction(**legacy_tx_values)
    # unsigned spoofed legacy transaction
    unsigned_legacy_spoofed = SpoofTransaction(unsigned_legacy)
    _validate_unsigned_spoofed(unsigned_legacy_spoofed)
    # signed spoofed legacy transaction
    signed_legacy_spoofed = SpoofTransaction(
        unsigned_legacy, from_=Address(b"\x00" * 20)
    )
    _validate_signed_spoofed_common(signed_legacy_spoofed)
    assert signed_legacy_spoofed.type_id is None

    unsigned_access_list = latest_txn_builder.new_unsigned_access_list_transaction(**access_list_tx_values)  # type: ignore  # noqa: E501
    # unsigned spoofed access list transaction
    unsigned_access_list_spoofed = SpoofTransaction(unsigned_access_list)
    _validate_unsigned_spoofed(unsigned_access_list_spoofed)
    # signed spoofed access list transaction
    signed_access_list_spoofed = SpoofTransaction(
        unsigned_access_list, from_=Address(b"\x00" * 20)
    )
    _validate_signed_spoofed_common(signed_access_list_spoofed)
    assert signed_access_list_spoofed.type_id == 1

    unsigned_dynamic = latest_txn_builder.new_unsigned_dynamic_fee_transaction(**dynamic_tx_values)  # type: ignore  # noqa: E501
    # unsigned spoofed dynamic fee transaction
    unsigned_dynamic_spoofed = SpoofTransaction(unsigned_dynamic)
    _validate_unsigned_spoofed(unsigned_dynamic_spoofed)
    # signed spoofed dynamic fee transaction
    signed_dynamic_spoofed = SpoofTransaction(
        unsigned_dynamic, from_=Address(b"\x00" * 20)
    )
    _validate_signed_spoofed_common(signed_dynamic_spoofed)
    assert signed_dynamic_spoofed.type_id == 2

    unsigned_blob = latest_txn_builder.new_unsigned_blob_transaction(**blob_tx_values)  # type: ignore  # noqa: E501
    # unsigned spoofed blob transaction
    unsigned_blob_spoofed = SpoofTransaction(unsigned_blob)
    _validate_unsigned_spoofed(unsigned_blob_spoofed)
    # signed spoofed blob transaction
    signed_blob_spoofed = SpoofTransaction(unsigned_blob, from_=Address(b"\x00" * 20))
    _validate_signed_spoofed_common(signed_blob_spoofed)
    assert signed_blob_spoofed.type_id == unsigned_blob._type_id == 3


def _validate_signed_spoofed_common(signed_spoofed):
    assert signed_spoofed.sender == Address(b"\x00" * 20)
    assert signed_spoofed.r == DEFAULT_SPOOF_R
    assert signed_spoofed.s == DEFAULT_SPOOF_S
    assert signed_spoofed.y_parity == DEFAULT_SPOOF_Y_PARITY


def _validate_unsigned_spoofed(unsigned_spoofed):
    assert not hasattr(unsigned_spoofed, "sender")
    assert not hasattr(unsigned_spoofed, "type_id")
    assert not hasattr(unsigned_spoofed, "r")
    assert not hasattr(unsigned_spoofed, "s")
    assert not hasattr(unsigned_spoofed, "y_parity")
