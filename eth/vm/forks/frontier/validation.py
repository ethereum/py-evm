from eth_utils import (
    ValidationError,
)

from eth.abc import (
    BlockHeaderAPI,
    SignedTransactionAPI,
    StateAPI,
    VirtualMachineAPI,
)


def validate_frontier_transaction(
    state: StateAPI, transaction: SignedTransactionAPI
) -> None:
    max_gas_cost = transaction.gas * state.get_gas_price(transaction)
    sender_balance = state.get_balance(transaction.sender)

    if sender_balance < max_gas_cost:
        raise ValidationError(
            f"Sender {transaction.sender!r} cannot afford txn gas "
            f"{max_gas_cost} with account balance {sender_balance}"
        )

    total_cost = transaction.value + max_gas_cost

    if sender_balance < total_cost:
        raise ValidationError(
            f"Sender does not have enough balance to cover transaction value and gas "
            f" (has {sender_balance}, needs {total_cost})"
        )

    sender_nonce = state.get_nonce(transaction.sender)
    if sender_nonce != transaction.nonce:
        raise ValidationError(
            f"Invalid transaction nonce: Expected {sender_nonce}, "
            f"but got {transaction.nonce}"
        )


def validate_frontier_transaction_against_header(
    _vm: VirtualMachineAPI,
    base_header: BlockHeaderAPI,
    transaction: SignedTransactionAPI,
) -> None:
    if base_header.gas_used + transaction.gas > base_header.gas_limit:
        raise ValidationError(
            f"Transaction exceeds gas limit: using {transaction.gas}, "
            f"bringing total to {base_header.gas_used + transaction.gas}, "
            f"but limit is {base_header.gas_limit}"
        )
