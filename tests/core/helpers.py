def new_transaction(vm, from_, to, amount, private_key, gas_price=10, gas=100000):
    """
    Create and return a transaction sending amount from <from_> to <to>.

    The transaction will be signed with the given private key.
    """
    with vm.state_db(read_only=True) as state_db:
        nonce = state_db.get_nonce(from_)
    tx = vm.create_unsigned_transaction(
        nonce=nonce, gas_price=gas_price, gas=gas, to=to, value=amount, data=b'')
    return tx.as_signed_transaction(private_key)
