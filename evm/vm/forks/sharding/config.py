from eth_utils import (
    to_wei,
)

from evm.utils import (
    env,
)


def get_sharding_config():
    return {
        # TODO: currently is fixed as 100 ETH, should be removed after
        # variable-sized deposit is implemented
        'DEPOSIT_SIZE': env.get(
            'PYEVM_SHARDING_DEPOSIT_SIZE',
            type=int,
            default=to_wei('100', 'ether'),
        ),
        # the maximum valid ahead periods from the current period for `get_eligible_proposer`
        'LOOKAHEAD_PERIODS': env.get('PYEVM_SHARDING_LOOKAHEAD_PERIODS', type=int, default=4),
        # the number of blocks in one `period`
        'PERIOD_LENGTH': env.get('PYEVM_SHARDING_PERIOD_LENGTH', type=int, default=5),
        # the gas limit of one collation
        'COLLATION_GASLIMIT': env.get(
            'PYEVM_SHARDING_COLLATION_GASLIMIT',
            type=int,
            default=10 ** 7,
        ),
        # the number of shards
        'SHARD_COUNT': env.get('PYEVM_SHARDING_SHARD_COUNT', type=int, default=100),
        # the gas limit of verifying a signature
        'SIG_GASLIMIT': env.get('PYEVM_SHARDING_SIG_GASLIMIT', type=int, default=40000),
        # the reward for creating a collation
        'COLLATOR_REWARD': env.get(
            'PYEVM_SHARDING_COLLATOR_REWARD',
            type=int,
            default=to_wei('0.001', 'ether'),
        ),
        # default gas_price
        'GAS_PRICE': env.get('PYEVM_SHARDING_GAS_PRICE', type=int, default=1),
        # default gas, just a large enough gas for vmc transactions
        'DEFAULT_GAS': env.get('PYEVM_SHARDING_DEFAULT_GAS', type=int, default=510000),
    }
