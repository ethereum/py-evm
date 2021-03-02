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
        nonce=None,
        chain_id=None):
    """
    Create and return a transaction sending amount from <from_> to <to>.

    The transaction will be signed with the given private key.
    """
    if nonce is None:
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


@curry
def new_access_list_transaction(
        vm,
        from_,
        to,
        private_key,
        amount=0,
        gas_price=10,
        gas=100000,
        data=b'',
        nonce=None,
        chain_id=1,
        access_list=None):
    """
    Create and return a transaction sending amount from <from_> to <to>.

    The transaction will be signed with the given private key.
    """
    if nonce is None:
        nonce = vm.state.get_nonce(from_)
    if access_list is None:
        access_list = []

    tx = vm.get_transaction_builder().new_unsigned_access_list_transaction(
        chain_id=chain_id,
        nonce=nonce,
        gas_price=gas_price,
        gas=gas,
        to=to,
        value=amount,
        data=data,
        access_list=access_list,
    )

    return tx.as_signed_transaction(private_key)
