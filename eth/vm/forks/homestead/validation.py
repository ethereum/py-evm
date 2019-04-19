from eth_utils import (
    ValidationError,
)

from eth.constants import (
    SECPK1_N,
)

from eth.typing import BaseOrSpoofTransaction
from eth.vm.forks.frontier.validation import (
    validate_frontier_transaction,
)
from eth.vm.state import BaseState


def validate_homestead_transaction(state: BaseState,
                                   transaction: BaseOrSpoofTransaction) -> None:
    if transaction.s > SECPK1_N // 2 or transaction.s == 0:
        raise ValidationError("Invalid signature S value")

    validate_frontier_transaction(state, transaction)
