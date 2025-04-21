import pytest

from eth_keys.datatypes import (
    PrivateKey,
)

from eth.chains.mainnet import (
    MAINNET_VMS,
)


# MAINNET_VMS from Berlin onwards (TypedTransaction introduced)
@pytest.mark.parametrize("vm", MAINNET_VMS[8:])
def test_legacy_transaction_implementations_across_all_forks(vm):
    unsigned = vm.block_class.transaction_builder.legacy_unsigned(
        nonce=0,
        gas_price=0,
        gas=0,
        to=b"",
        value=0,
        data=b"",
    )
    signed = unsigned.as_signed_transaction(
        private_key=PrivateKey(b"\x01" * 32),
        chain_id=1,
    )
    assert isinstance(signed, vm.block_class.transaction_builder.legacy_signed)
