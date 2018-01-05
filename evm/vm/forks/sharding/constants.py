from eth_utils import (
    to_wei,
)

#
# VMC specific
#

# TODO: currently is fixed as 100 ETH, should be removed after
# variable-sized deposit is implemented
DEPOSIT_SIZE = to_wei('100', 'ether')
# the maximum valid ahead periods from the current period for `get_eligible_proposer`
LOOKAHEAD_PERIODS = 4
# the number of blocks in one `period`
PERIOD_LENGTH = 5
# the gas limit of one collation
COLLATION_GASLIMIT = 10 ** 7
# the number of shards
SHARD_COUNT = 100
# the gas limit of verifying a signature
SIG_GASLIMIT = 40000
# the reward for creating a collation
COLLATOR_REWARD = to_wei('0.001', 'ether')
