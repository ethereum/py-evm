import sys

from eth_utils.toolz import curry

import pytest

from eth_utils import (
    decode_hex,
    ValidationError,
)

from eth.chains.base import MiningChain

from eth.vm.spoof import (
    SpoofTransaction,
)


greater_equal_python36 = pytest.mark.skipif(
    sys.version_info < (3, 6),
    reason="requires python3.6 or higher"
)


@curry
def new_transaction(
        vm,
        from_,
        to,
        amount=0,
        private_key=None,
        gas_price=10,
        gas=100000,
        data=b'',
        chain_id=None):
    """
    Create and return a transaction sending amount from <from_> to <to>.

    The transaction will be signed with the given private key.
    """
    nonce = vm.state.account_db.get_nonce(from_)
    tx = vm.create_unsigned_transaction(
        nonce=nonce,
        gas_price=gas_price,
        gas=gas,
        to=to,
        value=amount,
        data=data,
    )
    if private_key:
        if chain_id is None:
            return tx.as_signed_transaction(private_key)
        else:
            return tx.as_signed_transaction(private_key, chain_id=chain_id)
    else:
        return SpoofTransaction(tx, from_=from_)


def fill_block(chain, from_, key, gas, data):
    if not isinstance(chain, MiningChain):
        pytest.skip("Cannot fill block automatically unless using a MiningChain")
        return

    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100

    vm = chain.get_vm()
    assert vm.block.header.gas_used == 0

    while True:
        tx = new_transaction(chain.get_vm(), from_, recipient, amount, key, gas=gas, data=data)
        try:
            chain.apply_transaction(tx)
        except ValidationError as exc:
            if str(exc).startswith("Transaction exceeds gas limit"):
                break
            else:
                raise exc

    assert chain.get_vm().block.header.gas_used > 0
