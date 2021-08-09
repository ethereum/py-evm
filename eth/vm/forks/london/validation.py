from eth.abc import (
    SignedTransactionAPI,
    StateAPI
)

from eth_utils.exceptions import ValidationError

def validate_london_normalized_transaction(
    state: StateAPI,
    transaction: SignedTransactionAPI,
    base_fee_per_gas: int
) -> None:
    """
    Validates a London normalized transaction.

    Raise `eth.exceptions.ValidationError` if the sender cannot
    afford to send this transaction.
    """
    if transaction.max_fee_per_gas < base_fee_per_gas:
        raise ValidationError(
            f"Sender's max fee per gas ({transaction.max_fee_per_gas}) is "
            f"lower than block's base fee per gas ({base_fee_per_gas})"
        )

    sender_balance = state.get_balance(transaction.sender)
    if sender_balance < transaction.value:
        # This check is redundant to the later total_transaction_cost check,
        #   but is helpful for clear error messages.
        raise ValidationError(
            f"Sender {transaction.sender!r} cannot afford txn value"
            f"{transaction.value} with account balance {sender_balance}"
        )

    priority_fee_per_gas = min(
        transaction.max_priority_fee_per_gas,
        transaction.max_fee_per_gas - base_fee_per_gas,
    )

    effective_gas_price = priority_fee_per_gas + base_fee_per_gas
    total_transaction_cost = transaction.value + effective_gas_price

    if sender_balance < total_transaction_cost:
        raise ValidationError(
            f"Sender does not have enough balance to cover transaction value and gas "
            f" (has {sender_balance}, needs {total_transaction_cost})"
        )
