from eth_utils import (
    ValidationError,
)

from eth.constants import (
    SECPK1_N,
)

from eth.db.account import BaseAccountDB

from eth.typing import BaseOrSpoofTransaction

from eth.vm.forks.frontier.validation import (
    validate_frontier_transaction,
)


def validate_homestead_transaction(account_db: BaseAccountDB,
                                   transaction: BaseOrSpoofTransaction) -> None:
    if transaction.s > SECPK1_N // 2 or transaction.s == 0:
        raise ValidationError("Invalid signature S value")

    validate_frontier_transaction(account_db, transaction)
