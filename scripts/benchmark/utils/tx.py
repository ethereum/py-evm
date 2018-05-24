from eth_typing import (
    Address
)

from evm.rlp.transactions import (
    BaseTransaction
)
from evm.vm.base import (
    VM
)

from eth_keys.datatypes import (
    PrivateKey
)


def new_transaction(
        vm: VM,
        from_: Address,
        to: Address,
        amount: int=0,
        private_key: PrivateKey=None,
        gas_price: int=10,
        gas: int=100000,
        data: bytes=b'') -> BaseTransaction:
    """
    Create and return a transaction sending amount from <from_> to <to>.

    The transaction will be signed with the given private key.
    """
    nonce = vm.state.account_db.get_nonce(from_)
    tx = vm.create_unsigned_transaction(
        nonce=nonce, gas_price=gas_price, gas=gas, to=to, value=amount, data=data)

    return tx.as_signed_transaction(private_key)
