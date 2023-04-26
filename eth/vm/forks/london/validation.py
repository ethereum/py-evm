from eth_utils.exceptions import (
    ValidationError,
)

from eth.abc import (
    SignedTransactionAPI,
    StateAPI,
)
from eth.vm.forks.homestead.validation import (
    validate_homestead_transaction,
)


def validate_london_normalized_transaction(
    state: StateAPI,
    transaction: SignedTransactionAPI,
) -> None:
    """
    Validates a London normalized transaction.

    Raise `eth.exceptions.ValidationError` if the sender cannot
    afford to send this transaction.
    """
    base_fee_per_gas = state.execution_context.base_fee_per_gas
    if transaction.max_fee_per_gas < base_fee_per_gas:
        raise ValidationError(
            f"Sender's max fee per gas ({transaction.max_fee_per_gas}) is "
            f"lower than block's base fee per gas ({base_fee_per_gas})"
        )

    validate_homestead_transaction(state, transaction)
