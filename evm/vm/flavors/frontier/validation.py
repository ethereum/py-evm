from evm.exceptions import (
    ValidationError,
)


def validate_frontier_transaction(vm, transaction):
    gas_cost = transaction.gas * transaction.gas_price
    sender_balance = vm.state_db.get_balance(transaction.sender)

    if sender_balance < gas_cost:
        raise ValidationError(
            "Sender account balance cannot afford txn gas: `{0}`".format(transaction.sender)
        )

    total_cost = transaction.value + gas_cost

    if sender_balance < total_cost:
        raise ValidationError("Sender account balance cannot afford txn")

    if vm.block.header.gas_used + transaction.gas > vm.block.header.gas_limit:
        raise ValidationError("Transaction exceeds gas limit")

    if vm.state_db.get_nonce(transaction.sender) != transaction.nonce:
        raise ValidationError("Invalid transaction nonce")
