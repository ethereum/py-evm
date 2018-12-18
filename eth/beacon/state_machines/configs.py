from typing import (
    NamedTuple,
)

from eth.typing import (
    Address,
)


BeaconConfig = NamedTuple(
    'BeaconConfig',
    (
        # Misc
        ('SHARD_COUNT', int),
        ('TARGET_COMMITTEE_SIZE', int),
        ('EJECTION_BALANCE', int),
        ('MAX_BALANCE_CHURN_QUOTIENT', int),
        ('BEACON_CHAIN_SHARD_NUMBER', int),
        ('BLS_WITHDRAWAL_PREFIX_BYTE', bytes),
        ('MAX_CASPER_VOTES', int),
        ('LATEST_BLOCK_ROOTS_LENGTH', int),
        # EMPTY_SIGNATURE is defined in constants.py
        # Deposit contract
        ('DEPOSIT_CONTRACT_ADDRESS', Address),
        ('DEPOSIT_CONTRACT_TREE_DEPTH', int),
        ('MIN_DEPOSIT', int),
        ('MAX_DEPOSIT', int),
        # ZERO_HASH (ZERO_HASH32) is defined in constants.py
        # Initial values
        ('INITIAL_FORK_VERSION', int),
        ('INITIAL_SLOT_NUMBER', int),
        # Time parameters
        ('SLOT_DURATION', int),
        ('MIN_ATTESTATION_INCLUSION_DELAY', int),
        ('EPOCH_LENGTH', int),
        ('MIN_VALIDATOR_REGISTRY_CHANGE_INTERVAL', int),
        ('POW_RECEIPT_ROOT_VOTING_PERIOD', int),
        ('SHARD_PERSISTENT_COMMITTEE_CHANGE_PERIOD', int),
        ('COLLECTIVE_PENALTY_CALCULATION_PERIOD', int),
        ('ZERO_BALANCE_VALIDATOR_TTL', int),
        # Reward and penalty quotients
        ('BASE_REWARD_QUOTIENT', int),
        ('WHISTLEBLOWER_REWARD_QUOTIENT', int),
        ('INCLUDER_REWARD_QUOTIENT', int),
        ('INACTIVITY_PENALTY_QUOTIENT', int),
        # Max operations per block
        ('MAX_PROPOSER_SLASHINGS', int),
        ('MAX_CASPER_SLASHINGS', int),
        ('MAX_ATTESTATIONS', int),
        ('MAX_DEPOSITS', int),
        ('MAX_EXITS', int),
    )
)
