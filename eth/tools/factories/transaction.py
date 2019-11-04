from eth_utils.toolz import curry

from eth.vm.spoof import (
    SpoofTransaction,
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
    nonce = vm.state.get_nonce(from_)
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
