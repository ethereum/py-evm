from evm.vm.forks.frontier.validation import (
    validate_frontier_transaction,
)


def validate_sharding_transaction(evm, transaction):
    # TODO:Update transaction validation logic in Sharding
    # e.g. checking shard_id < SHARD_COUNT

    # `validate_homestead_transaction` assumes underlying signature scheme
    # to be ECDSA and checks signatures accordingly. So it's skipped for
    # the reason that there won't be built-in signature scheme in Account
    # Abstraction.
    validate_frontier_transaction(evm, transaction)
