from eth.constants import (
    ZERO_ADDRESS,
)
from eth.beacon.state_machines.configs import BeaconConfig


SERENITY_CONFIG = BeaconConfig(
    # Misc
    SHARD_COUNT=2**10,  # (= 1,024) shards
    TARGET_COMMITTEE_SIZE=2**8,  # (= 256) validators
    MAX_ATTESTATIONS_PER_BLOCK=2**7,  # (= 128) attestations
    MIN_BALANCE=2**4,  # (= 16) ETH
    MAX_BALANCE_CHURN_QUOTIENT=2**5,  # (= 32)
    GWEI_PER_ETH=10**9,  # Gwei/ETH
    BEACON_CHAIN_SHARD_NUMBER=2**64 - 1,
    BLS_WITHDRAWAL_CREDENTIALS=b'\x00',
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
    BASE_REWARD_QUOTIENT=2**11,  # (= 2,048)
    WHISTLEBLOWER_REWARD_QUOTIENT=2**9,  # (= 512)
    INCLUDER_REWARD_QUOTIENT=2**3,  # (= 8)
    INACTIVITY_PENALTY_QUOTIENT=2**34,  # (= 17,179,869,184)
)
