from eth.constants import (
    SECPK1_N,
)
from eth.exceptions import (
    ValidationError,
)

from eth.vm.forks.frontier.validation import (
    validate_frontier_transaction,
)


def validate_homestead_transaction(account_db, transaction):
    if transaction.s > SECPK1_N // 2 or transaction.s == 0:
        raise ValidationError("Invalid signature S value")

    validate_frontier_transaction(account_db, transaction)
