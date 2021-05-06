from eth.vm.forks.london.blocks import LondonBlockHeader
from eth.abc import (
    SignedTransactionAPI,
    StateAPI
)

from eth_utils.exceptions import ValidationError

from .transactions import LondonNormalizedTransaction, LondonTypedTransaction


class LondonValidatedTransaction(LondonNormalizedTransaction):
    """
    A London normalized transaction with additional `effective_gas_price`
    and `priority_fee_per_gas` attributes for easier processing.
    """
    def __init__(
        self,
        effective_gas_price: int,
        priority_fee_per_gas: int,
        **kwargs
    ):
        self.effective_gas_price = effective_gas_price
        self.priority_fee_per_gas = priority_fee_per_gas
        super().__init__(**kwargs)


def validate_london_normalized_transaction(
    state: StateAPI,
    transaction: LondonNormalizedTransaction,
    header: LondonBlockHeader
) -> LondonValidatedTransaction:
    """
    Validates a London normalized transaction.

    Raise `eth.exceptions.ValidationError` if the sender cannot
    afford to send this transaction.

    Returns a LondonValidatedTransaction.
    """
    if transaction.max_fee_per_gas < header.base_fee_per_gas:
        raise ValidationError(
            f"Sender's max fee per gas ({transaction.max_fee_per_gas}) is "
            f"lower than block's base fee per gas ({header.base_fee_per_gas})"
        )

    sender_balance = state.get_balance(transaction.sender)
    if transaction.value > sender_balance:
        raise ValidationError(
            f"Sender {transaction.sender!r} cannot afford txn value"
            f"{transaction.value} with account balance {sender_balance}"
        )

    priority_fee_per_gas = min(
        transaction.max_priority_fee_per_gas,
        transaction.max_fee_per_gas - header.base_fee_per_gas
    )

    effective_gas_price = priority_fee_per_gas + header.base_fee_per_gas
    total_transaction_cost = transaction.value + effective_gas_price

    if sender_balance - total_transaction_cost < 0:
        raise ValidationError(
            f"Sender does not have enough balance to cover transaction value and gas "
            f" (has {sender_balance}, needs {total_transaction_cost})"
        )

    return transaction.as_validated_transaction(
        effective_gas_price, priority_fee_per_gas
    )