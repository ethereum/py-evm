from eth.constants import (
    ZERO_ADDRESS,
)

from eth2.beacon.configs import BeaconConfig
from eth2.beacon.constants import (
    GWEI_PER_ETH,
)
from eth2.beacon.helpers import slot_to_epoch
from eth2.beacon.typing import (
    Gwei,
    Second,
    ShardNumber,
    SlotNumber,
)


SERENITY_CONFIG = BeaconConfig(
    # Misc
    SHARD_COUNT=2**10,  # (= 1,024) shards
    TARGET_COMMITTEE_SIZE=2**7,  # (= 128) validators
    EJECTION_BALANCE=Gwei(2**4 * GWEI_PER_ETH),  # (= 16,000,000,000) Gwei
    MAX_BALANCE_CHURN_QUOTIENT=2**5,  # (= 32)
    BEACON_CHAIN_SHARD_NUMBER=ShardNumber(2**64 - 1),
    MAX_INDICES_PER_SLASHABLE_VOTE=2**12,  # (= 4,096) votes
    LATEST_BLOCK_ROOTS_LENGTH=2**13,  # (= 8,192) slots
    LATEST_INDEX_ROOTS_LENGTH=2**13,  # (= 8,192) epochs
    LATEST_RANDAO_MIXES_LENGTH=2**13,  # (= 8,192) epochs
    LATEST_PENALIZED_EXIT_LENGTH=2**13,  # (= 8,192) epochs
    # Deposit contract
    DEPOSIT_CONTRACT_ADDRESS=ZERO_ADDRESS,  # TBD
    DEPOSIT_CONTRACT_TREE_DEPTH=2**5,  # (= 32)
    MIN_DEPOSIT_AMOUNT=Gwei(2**0 * GWEI_PER_ETH),  # (= 1,000,000,000) Gwei
    MAX_DEPOSIT_AMOUNT=Gwei(2**5 * GWEI_PER_ETH),  # (= 32,000,000,00) Gwei
    # Initial values
    GENESIS_FORK_VERSION=0,
    GENESIS_SLOT=SlotNumber(0),
    GENESIS_EPOCH=slot_to_epoch(SlotNumber(0), 2**6),  # GENESIS_EPOCH=slot_to_epoch(GENESIS_SLOT)
    GENESIS_START_SHARD=ShardNumber(0),
    BLS_WITHDRAWAL_PREFIX_BYTE=b'\x00',
    # Time parameters
    SLOT_DURATION=Second(6),  # seconds
    MIN_ATTESTATION_INCLUSION_DELAY=2**2,  # (= 4) slots
    EPOCH_LENGTH=2**6,  # (= 64) slots
    SEED_LOOKAHEAD=2**0,  # (= 1) epochs
    ENTRY_EXIT_DELAY=2**2,  # (= 4) epochs
    ETH1_DATA_VOTING_PERIOD=2**4,  # (= 16) epochs
    MIN_VALIDATOR_WITHDRAWAL_TIME=2**8,  # (= 256) epochs
    # Reward and penalty quotients
    BASE_REWARD_QUOTIENT=2**10,  # (= 1,024)
    WHISTLEBLOWER_REWARD_QUOTIENT=2**9,  # (= 512)
    INCLUDER_REWARD_QUOTIENT=2**3,  # (= 8)
    INACTIVITY_PENALTY_QUOTIENT=2**24,  # (= 16,777,216)
    # Max operations per block
    MAX_PROPOSER_SLASHINGS=2**4,  # (= 16)
    MAX_ATTESTER_SLASHINGS=2**0,  # (= 1)
    MAX_ATTESTATIONS=2**7,  # (= 128)
    MAX_DEPOSITS=2**4,  # (= 16)
    MAX_EXITS=2**4,  # (= 16)
)
