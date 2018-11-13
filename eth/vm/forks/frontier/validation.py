from eth_utils import (
    ValidationError,
)

from eth.db.account import BaseAccountDB

from eth.rlp.headers import BlockHeader

from eth.rlp.transactions import BaseTransaction

from eth.typing import (
    BaseOrSpoofTransaction
)

from eth.vm.base import BaseVM


def validate_frontier_transaction(account_db: BaseAccountDB,
                                  transaction: BaseOrSpoofTransaction) -> None:
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


def validate_frontier_transaction_against_header(_vm: BaseVM,
                                                 base_header: BlockHeader,
                                                 transaction: BaseTransaction) -> None:
    if base_header.gas_used + transaction.gas > base_header.gas_limit:
        raise ValidationError(
            "Transaction exceeds gas limit: using {}, bringing total to {}, but limit is {}".format(
                transaction.gas,
                base_header.gas_used + transaction.gas,
                base_header.gas_limit,
            )
        )
