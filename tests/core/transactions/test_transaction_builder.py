import pytest

from eth_keys.datatypes import (
    PrivateKey,
)
from eth_utils.toolz import (
    merge,
)

from eth.chains.mainnet import (
    MAINNET_VMS,
)
from eth.vm.forks import (
    BerlinVM,
    CancunVM,
    LondonVM,
    PragueVM,
)
from eth.vm.forks.prague.transactions import (
    Authorization,
    PragueTransactionBuilder,
    PragueTypedTransaction,
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

    unsigned_tx_dict = {
        "chain_id": 1,
        "nonce": 1,
        "max_priority_fee_per_gas": 1,
        "max_fee_per_gas": 1,
        "gas": 1,
        "to": b"\x00" * 20,
        "value": 1,
        "data": b"\x00" * 32 + b"\x01",
        "access_list": [(b"\x00" * 20, (0, 1))],
        "authorization_list": authorization_list,
    }
    unsigned_set_code_tx = builder.new_unsigned_set_code_transaction(**unsigned_tx_dict)

    key = PrivateKey(b"\x01" * 32)
    set_code_tx = unsigned_set_code_tx.as_signed_transaction(
        private_key=key,
        chain_id=1,
    )
    assert isinstance(set_code_tx, PragueTypedTransaction)

    signed_set_code_dict = merge(
        unsigned_tx_dict,
        {
            "y_parity": set_code_tx.y_parity,
            "r": set_code_tx.r,
            "s": set_code_tx.s,
        },
    )
    built_set_code_tx = builder.new_set_code_transaction(**signed_set_code_dict)

    assert set_code_tx == built_set_code_tx


# mainnet VMs starting from Berlin (TypedTransaction introduced)
@pytest.mark.parametrize("vm_class", MAINNET_VMS[8:])
def test_transaction_builder_methods(vm_class):
    builder = vm_class.get_transaction_builder()

    builder_dir = dir(builder)
    new_tx_methods = {
        method
        for method in builder_dir
        if method.startswith("new") and callable(getattr(builder, method))
    }
    assert len(new_tx_methods) > 0, f"no builder methods for `{vm_class}`"

    transaction_types = 0
    if issubclass(vm_class, BerlinVM):
        new_tx_methods.difference_update(
            {
                "new_transaction",  # legacy
                "new_access_list_transaction",
                "new_unsigned_access_list_transaction",
            }
        )
        transaction_types += 1
    if issubclass(vm_class, LondonVM):
        new_tx_methods.difference_update(
            {"new_dynamic_fee_transaction", "new_unsigned_dynamic_fee_transaction"}
        )
        transaction_types += 1
    if issubclass(vm_class, CancunVM):
        new_tx_methods.difference_update(
            {"new_blob_transaction", "new_unsigned_blob_transaction"}
        )
        transaction_types += 1
    if issubclass(vm_class, PragueVM):
        new_tx_methods.difference_update(
            {"new_set_code_transaction", "new_unsigned_set_code_transaction"}
        )
        transaction_types += 1

    assert len(new_tx_methods) == 0

    if len(builder.typed_transaction.decoders.keys()) != transaction_types:
        # Add new methods and make sure `nex_x_transaction` method returns a
        # `TypedTransaction`, following the pattern of the other VMs
        raise AssertionError(
            f"Likely missing new transaction methods in {vm_class} builder."
        )
