from eth.constants import (
    ZERO_ADDRESS,
)
from eth.beacon.state_machines.configs import BeaconConfig


SERENITY_CONFIG = BeaconConfig(
    # Misc
    SHARD_COUNT=2**10,  # (= 1,024) shards
    TARGET_COMMITTEE_SIZE=2**8,  # (= 256) validators
    EJECTION_BALANCE=2**4,  # (= 16) ETH
    MAX_BALANCE_CHURN_QUOTIENT=2**5,  # (= 32)
    BEACON_CHAIN_SHARD_NUMBER=2**64 - 1,
    BLS_WITHDRAWAL_PREFIX_BYTE=b'\x00',
    MAX_CASPER_VOTES=2**10,  # (= 1,024) votes
    LATEST_BLOCK_ROOTS_LENGTH=2**13,  # (= 8,192) block roots
    # Deposit contract
    DEPOSIT_CONTRACT_ADDRESS=ZERO_ADDRESS,  # TBD
    DEPOSIT_CONTRACT_TREE_DEPTH=2**5,  # (= 32)
    MIN_DEPOSIT=2**0,  # (= 1) ETH
    MAX_DEPOSIT=2**5,  # (= 32) ETH
    # Initial values
    INITIAL_FORK_VERSION=0,
    INITIAL_SLOT_NUMBER=0,
    # Time parameters
    SLOT_DURATION=6,  # seconds
    MIN_ATTESTATION_INCLUSION_DELAY=2**2,  # (= 4) slots
    EPOCH_LENGTH=2**6,  # (= 64) slots
    MIN_VALIDATOR_REGISTRY_CHANGE_INTERVAL=2**8,  # (= 256) slots
    POW_RECEIPT_ROOT_VOTING_PERIOD=2**10,  # (= 1,024) slots
    SHARD_PERSISTENT_COMMITTEE_CHANGE_PERIOD=2**17,  # (= 131,072) slots
    COLLECTIVE_PENALTY_CALCULATION_PERIOD=2**20,  # (= 1,048,576) slots
    ZERO_BALANCE_VALIDATOR_TTL=2**22,  # (= 4,194,304) slots
    # Reward and penalty quotients
    BASE_REWARD_QUOTIENT=2**10,  # (= 1,024)
    WHISTLEBLOWER_REWARD_QUOTIENT=2**9,  # (= 512)
    INCLUDER_REWARD_QUOTIENT=2**3,  # (= 8)
    INACTIVITY_PENALTY_QUOTIENT=2**34,  # (= 17,179,869,184)
    # Max operations per block
    MAX_PROPOSER_SLASHINGS=2**4,  # (= 16)
    MAX_CASPER_SLASHINGS=2**4,  # (= 16)
    MAX_ATTESTATIONS=2**7,  # (= 128)
    MAX_DEPOSITS=2**4,  # (= 16)
    MAX_EXITS=2**4,  # (= 16)
)
