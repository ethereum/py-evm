from typing import (
    NamedTuple,
)

from eth.typing import (
    Address,
)
from eth2.beacon.typing import (
    SlotNumber,
    ShardNumber,
    Ether,
    Second,
)


BeaconConfig = NamedTuple(
    'BeaconConfig',
    (
        # Misc
        ('SHARD_COUNT', int),
        ('TARGET_COMMITTEE_SIZE', int),
        ('EJECTION_BALANCE', Ether),
        ('MAX_BALANCE_CHURN_QUOTIENT', int),
        ('BEACON_CHAIN_SHARD_NUMBER', ShardNumber),
        ('MAX_CASPER_VOTES', int),
        ('LATEST_BLOCK_ROOTS_LENGTH', int),
        ('LATEST_RANDAO_MIXES_LENGTH', int),
        ('LATEST_PENALIZED_EXIT_LENGTH', int),
        # EMPTY_SIGNATURE is defined in constants.py
        # Deposit contract
        ('DEPOSIT_CONTRACT_ADDRESS', Address),
        ('DEPOSIT_CONTRACT_TREE_DEPTH', int),
        ('MIN_DEPOSIT', Ether),
        ('MAX_DEPOSIT', Ether),
        # ZERO_HASH (ZERO_HASH32) is defined in constants.py
        # Initial values
        ('GENESIS_FORK_VERSION', int),
        ('GENESIS_SLOT', SlotNumber),
        ('BLS_WITHDRAWAL_PREFIX_BYTE', bytes),
        # Time parameters
        ('SLOT_DURATION', Second),
        ('MIN_ATTESTATION_INCLUSION_DELAY', int),
        ('EPOCH_LENGTH', int),
        ('SEED_LOOKAHEAD', int),
        ('ENTRY_EXIT_DELAY', int),
        ('ETH1_DATA_VOTING_PERIOD', int),
        ('MIN_VALIDATOR_WITHDRAWAL_TIME', int),
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
