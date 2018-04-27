from cytoolz import curry

from eth_utils import decode_hex

from evm.exceptions import (
    ValidationError,
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
        data=b''):
    """
    Create and return a transaction sending amount from <from_> to <to>.

    The transaction will be signed with the given private key.
    """
    nonce = vm.state.read_only_state_db.get_nonce(from_)
    tx = vm.create_unsigned_transaction(
        nonce=nonce, gas_price=gas_price, gas=gas, to=to, value=amount, data=data)
    if private_key:
        return tx.as_signed_transaction(private_key, chain_id=1)
    else:
        return tx


def fill_block(chain, from_, key, gas, data):
    recipient = decode_hex('0xa94f5374fce5edbc8e2a8697c15331677e6ebf0c')
    amount = 100

    vm = chain.get_vm()
    assert vm.state.gas_used == 0

    while True:
        tx = new_transaction(chain.get_vm(), from_, recipient, amount, key, gas=gas, data=data)
        try:
            chain.apply_transaction(tx)
        except ValidationError as exc:
            if "Transaction exceeds gas limit" == str(exc):
                break
            else:
                raise exc

    assert chain.get_vm().state.gas_used > 0


def apply_state_dict(account_db, state_dict):
    for account, account_data in state_dict.items():
        account_db.set_balance(account, account_data["balance"])
        account_db.set_nonce(account, account_data["nonce"])
        account_db.set_code(account, account_data["code"])

        for slot, value in account_data["storage"].items():
            account_db.set_storage(account, slot, value)
