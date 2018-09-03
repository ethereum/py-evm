from eth_utils import (
    ValidationError,
)

# in Frontier VM
# before executed, check there is delegatee
def validate_stamina_transaction(account_db, transaction, delegatee):
    gas_cost = transaction.gas * transaction.gas_price

    # not implemented
    delegatee_stamina = vm.get_stamina(delegatee)

    sender_balance = account_db.get_balance(transaction.sender)

    if delegatee_stamina < gas_cost:
        raise ValidationError(
            "Delegatee account stamina cannot afford txn gas: `{0}`".format(transaction.sender)
        )

    if sender_balance < transaction.value:
        raise ValidationError("Sender account balance cannot afford txn")

    if account_db.get_nonce(transaction.sender) != transaction.nonce:
        raise ValidationError("Invalid transaction nonce")

def validate_frontier_transaction(account_db, transaction):
    gas_cost = transaction.gas * transaction.gas_price
    sender_balance = account_db.get_balance(transaction.sender)

    if sender_balance < gas_cost:
        raise ValidationError(
            "Sender account balance cannot afford txn gas: `{0}`".format(transaction.sender)
        )

    total_cost = transaction.value + gas_cost

    if sender_balance < total_cost:
        raise ValidationError("Sender account balance cannot afford txn")

    if account_db.get_nonce(transaction.sender) != transaction.nonce:
        raise ValidationError("Invalid transaction nonce")


def validate_frontier_transaction_against_header(_vm, base_header, transaction):
    if base_header.gas_used + transaction.gas > base_header.gas_limit:
        raise ValidationError(
            "Transaction exceeds gas limit: using {}, bringing total to {}, but limit is {}".format(
                transaction.gas,
                base_header.gas_used + transaction.gas,
                base_header.gas_limit,
            )
        )
