from eth_utils import (
    ValidationError,
)

from eth.abc import (
    BlockHeaderAPI,
    SignedTransactionAPI,
    StateAPI,
    VirtualMachineAPI,
)


def validate_frontier_transaction(state: StateAPI,
                                  transaction: SignedTransactionAPI) -> None:
    gas_cost = transaction.gas * transaction.gas_price
    sender_balance = state.get_balance(transaction.sender)

    if sender_balance < gas_cost:
        raise ValidationError(
            "Sender {} cannot afford txn gas {} with account balance {}".format(
                transaction.sender,
                gas_cost,
                sender_balance,
            )
        )

    total_cost = transaction.value + gas_cost

    if sender_balance < total_cost:
        raise ValidationError("Sender account balance cannot afford txn")

    if state.get_nonce(transaction.sender) != transaction.nonce:
        raise ValidationError("Invalid transaction nonce")


def validate_frontier_transaction_against_header(_vm: VirtualMachineAPI,
                                                 base_header: BlockHeaderAPI,
                                                 transaction: SignedTransactionAPI) -> None:
    if base_header.gas_used + transaction.gas > base_header.gas_limit:
        raise ValidationError(
            "Transaction exceeds gas limit: using {}, bringing total to {}, but limit is {}".format(
                transaction.gas,
                base_header.gas_used + transaction.gas,
                base_header.gas_limit,
            )
        )
