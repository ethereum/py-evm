from evm.exceptions import (
    ValidationError,
)
from evm.validation import (
    validate_transaction_access_list,
)


def validate_sharding_transaction(vm, transaction):
    gas_cost = transaction.gas * transaction.gas_price
    with vm.state.state_db(read_only=True) as state_db:
        txn_initiator_balance = state_db.get_balance(transaction.to)

    if txn_initiator_balance < gas_cost:
        raise ValidationError(
            "Transaction initiator account balance cannot afford txn gas: `{0}`".format(transaction.to)  # noqa: E501
        )

    if vm.block.header.gas_used + transaction.gas > vm.block.header.gas_limit:
        raise ValidationError("Transaction exceeds gas limit")

    validate_transaction_access_list(transaction.access_list)

    # TODO:Add transaction validation logic for Sharding
    # e.g. checking shard_id < SHARD_COUNT
