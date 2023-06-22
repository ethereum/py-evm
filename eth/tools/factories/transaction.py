from typing import (
    Sequence,
    Tuple,
    Union,
)

from eth_keys.datatypes import (
    PrivateKey,
)
from eth_typing import (
    Address,
)
from eth_utils.toolz import (
    curry,
)

from eth.abc import (
    SignedTransactionAPI,
)
from eth.vm.base import (
    VM,
)
from eth.vm.forks.berlin.transactions import (
    AccessListTransaction,
)
from eth.vm.forks.london.transactions import (
    DynamicFeeTransaction,
)
from eth.vm.spoof import (
    SpoofTransaction,
)


@curry
def new_transaction(
    vm: VM,
    from_: Address,
    to: Address,
    amount: int = 0,
    private_key: PrivateKey = None,
    gas_price: int = 10**10,  # 10 gwei, to easily cover initial London fee of 1 gwei
    gas: int = 100000,
    data: bytes = b"",
    nonce: int = None,
    chain_id: int = None,
) -> Union[SignedTransactionAPI, SpoofTransaction]:
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
        return tx.as_signed_transaction(private_key, chain_id=chain_id)
    else:
        return SpoofTransaction(tx, from_=from_)


@curry
def new_access_list_transaction(
    vm: VM,
    from_: Address,
    to: Address,
    private_key: PrivateKey,
    amount: int = 0,
    gas_price: int = 10**10,
    gas: int = 100000,
    data: bytes = b"",
    nonce: int = None,
    chain_id: int = 1,
    access_list: Sequence[Tuple[Address, Sequence[int]]] = None,
) -> AccessListTransaction:
    """
    Create and return a transaction sending amount from <from_> to <to>.

    The transaction will be signed with the given private key.
    """
    if nonce is None:
        nonce = vm.state.get_nonce(from_)
    if access_list is None:
        access_list = []

    tx = vm.get_transaction_builder().new_unsigned_access_list_transaction(  # type: ignore # noqa: E501
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


@curry
def new_dynamic_fee_transaction(
    vm: VM,
    from_: Address,
    to: Address,
    private_key: PrivateKey,
    amount: int = 0,
    max_priority_fee_per_gas: int = 1,
    max_fee_per_gas: int = 10**10,
    gas: int = 100000,
    data: bytes = b"",
    nonce: int = None,
    chain_id: int = 1,
    access_list: Sequence[Tuple[Address, Sequence[int]]] = None,
) -> DynamicFeeTransaction:
    """
    Create and return a transaction sending amount from <from_> to <to>.

    The transaction will be signed with the given private key.
    """
    if nonce is None:
        nonce = vm.state.get_nonce(from_)
    if access_list is None:
        access_list = []

    tx = vm.get_transaction_builder().new_unsigned_dynamic_fee_transaction(  # type: ignore # noqa: E501
        chain_id=chain_id,
        nonce=nonce,
        max_priority_fee_per_gas=max_priority_fee_per_gas,
        max_fee_per_gas=max_fee_per_gas,
        gas=gas,
        to=to,
        value=amount,
        data=data,
        access_list=access_list,
    )

    return tx.as_signed_transaction(private_key)
