from evm.exceptions import (
    ValidationError,
)
from evm.validation import (
    validate_transaction_access_list,
)


def validate_sharding_transaction(state, transaction):
    if state.gas_used + transaction.gas > state.gas_limit:
        raise ValidationError("Transaction exceeds gas limit")

    validate_transaction_access_list(transaction.access_list)

    # TODO:Add transaction validation logic for Sharding
    # e.g. checking shard_id < SHARD_COUNT
