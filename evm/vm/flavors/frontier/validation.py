from evm.exceptions import (
    InvalidTransaction,
)


def validate_frontier_transaction(evm, transaction):
    gas_cost = transaction.gas * transaction.gas_price
    sender_balance = evm.block.state_db.get_balance(transaction.sender)

    if sender_balance < gas_cost:
        raise InvalidTransaction(
            "Sender account balance cannot afford txn gas: `{0}`".format(transaction.sender)
        )

    total_cost = transaction.value + gas_cost

    if sender_balance < total_cost:
        raise InvalidTransaction("Sender account balance cannot afford txn")

    if transaction.gas > evm.block.header.gas_limit:
        raise InvalidTransaction("Transaction exceeds gas limit")

    if evm.block.state_db.get_nonce(transaction.sender) != transaction.nonce:
        raise InvalidTransaction("Invalid transaction nonce")
