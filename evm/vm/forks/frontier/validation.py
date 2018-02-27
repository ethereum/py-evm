from evm.exceptions import (
    ValidationError,
)


def validate_frontier_transaction(vm_state, transaction):
    gas_cost = transaction.gas * transaction.gas_price
    sender_balance = vm_state.read_only_state_db.get_balance(transaction.sender)

    if sender_balance < gas_cost:
        raise ValidationError(
            "Sender account balance cannot afford txn gas: `{0}`".format(transaction.sender)
        )

    total_cost = transaction.value + gas_cost

    if sender_balance < total_cost:
        raise ValidationError("Sender account balance cannot afford txn")

    if vm_state.gas_used + transaction.gas > vm_state.gas_limit:
        raise ValidationError("Transaction exceeds gas limit")

    if vm_state.read_only_state_db.get_nonce(transaction.sender) != transaction.nonce:
        raise ValidationError("Invalid transaction nonce")
