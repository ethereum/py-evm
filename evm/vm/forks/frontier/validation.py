from evm.exceptions import (
    ValidationError,
)


def validate_frontier_transaction(state, transaction):
    gas_cost = transaction.gas * transaction.gas_price
    sender_balance = state.account_db.get_balance(transaction.sender)

    if sender_balance < gas_cost:
        raise ValidationError(
            "Sender account balance cannot afford txn gas: `{0}`".format(transaction.sender)
        )

    total_cost = transaction.value + gas_cost

    if sender_balance < total_cost:
        raise ValidationError("Sender account balance cannot afford txn")

    if state.gas_used + transaction.gas > state.gas_limit:
        raise ValidationError("Transaction exceeds gas limit")

    if state.account_db.get_nonce(transaction.sender) != transaction.nonce:
        raise ValidationError("Invalid transaction nonce")
