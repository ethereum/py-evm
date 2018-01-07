import os

from eth_utils import (
    to_wei,
)


def get_sharding_config():
    return {
        # TODO: currently is fixed as 100 ETH, should be removed after
        # variable-sized deposit is implemented
        'DEPOSIT_SIZE': int(
            os.environ.get(
                'PYEVM_SHARDING_DEPOSIT_SIZE',
                to_wei('100', 'ether'),
            )
        ),
        # the maximum valid ahead periods from the current period for `get_eligible_proposer`
        'LOOKAHEAD_PERIODS': int(os.environ.get('PYEVM_SHARDING_LOOKAHEAD_PERIODS', 4)),
        # the number of blocks in one `period`
        'PERIOD_LENGTH': int(os.environ.get('PYEVM_SHARDING_PERIOD_LENGTH', 5)),
        # the gas limit of one collation
        'COLLATION_GASLIMIT': int(os.environ.get('PYEVM_SHARDING_COLLATION_GASLIMIT', 10 ** 7)),
        # the number of shards
        'SHARD_COUNT': int(os.environ.get('PYEVM_SHARDING_SHARD_COUNT', 100)),
        # the gas limit of verifying a signature
        'SIG_GASLIMIT': int(os.environ.get('PYEVM_SHARDING_SIG_GASLIMIT', 40000)),
        # the reward for creating a collation
        'COLLATOR_REWARD': int(
            os.environ.get(
                'PYEVM_SHARDING_COLLATOR_REWARD',
                to_wei('0.001', 'ether'),
            )
        ),
    }
