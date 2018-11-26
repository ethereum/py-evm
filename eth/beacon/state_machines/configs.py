from typing import (
    NamedTuple,
)

from eth.typing import (
    Address,
)


BeaconConfig = NamedTuple(
    'BeaconConfig',
    (
        ('SHARD_COUNT', int),  # shards
        ('DEPOSIT_SIZE', int),  # ETH
        ('MIN_ONLINE_DEPOSIT_SIZE', int),  # ETH
        ('DEPOSIT_CONTRACT_ADDRESS', Address),
        ('TARGET_COMMITTEE_SIZE', int),  # validators
        ('SLOT_DURATION', int),  # seconds
        ('CYCLE_LENGTH', int),  # slots
        ('MIN_VALIDATOR_SET_CHANGE_INTERVAL', int),  # slots
        ('SHARD_PERSISTENT_COMMITTEE_CHANGE_PERIOD', int),  # slots
        ('MIN_ATTESTATION_INCLUSION_DELAY', int),  # slots
        ('RANDAO_SLOTS_PER_LAYER', int),  # slots
        ('SQRT_E_DROP_TIME', int),  # slots
        ('WITHDRAWALS_PER_CYCLE', int),  # validators
        ('MIN_WITHDRAWAL_PERIOD', int),  # slots
        ('DELETION_PERIOD', int),  # slots
        ('COLLECTIVE_PENALTY_CALCULATION_PERIOD', int),  # slots
        ('POW_RECEIPT_ROOT_VOTING_PERIOD', int),  # slots
        ('SLASHING_WHISTLEBLOWER_REWARD_DENOMINATOR', int),
        ('BASE_REWARD_QUOTIENT', int),
        ('MAX_VALIDATOR_CHURN_QUOTIENT', int),
        ('POW_CONTRACT_MERKLE_TREE_DEPTH', int),
        ('LOGOUT_MESSAGE', str),
        ('INITIAL_FORK_VERSION', int),
    )
)
