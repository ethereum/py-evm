from eth.constants import (
    ZERO_ADDRESS,
)

from eth2.configs import Eth2Config
from eth2.beacon.constants import (
    GWEI_PER_ETH,
)
from eth2.beacon.helpers import slot_to_epoch
from eth2.beacon.typing import (
    Gwei,
    Second,
    Shard,
    Slot,
)

GENESIS_SLOT = Slot(2**32)
SLOTS_PER_EPOCH = 2**6


SERENITY_CONFIG = Eth2Config(
    # Misc
    SHARD_COUNT=2**10,  # (= 1,024) shards
    TARGET_COMMITTEE_SIZE=2**7,  # (= 128) validators
    MAX_BALANCE_CHURN_QUOTIENT=2**5,  # (= 32)
    MAX_INDICES_PER_SLASHABLE_VOTE=2**12,  # (= 4,096) votes
    MAX_EXIT_DEQUEUES_PER_EPOCH=2**2,  # (= 4)
    SHUFFLE_ROUND_COUNT=90,
    # Deposit contract
    DEPOSIT_CONTRACT_ADDRESS=ZERO_ADDRESS,  # TBD
    DEPOSIT_CONTRACT_TREE_DEPTH=2**5,  # (= 32)
    # Gwei values
    MIN_DEPOSIT_AMOUNT=Gwei(2**0 * GWEI_PER_ETH),  # (= 1,000,000,000) Gwei
    MAX_DEPOSIT_AMOUNT=Gwei(2**5 * GWEI_PER_ETH),  # (= 32,000,000,00) Gwei
    FORK_CHOICE_BALANCE_INCREMENT=Gwei(2**0 * GWEI_PER_ETH),  # (= 1,000,000,000) Gwei
    EJECTION_BALANCE=Gwei(2**4 * GWEI_PER_ETH),  # (= 16,000,000,000) Gwei
    # Initial values
    GENESIS_FORK_VERSION=0,
    GENESIS_SLOT=GENESIS_SLOT,
    GENESIS_EPOCH=slot_to_epoch(GENESIS_SLOT, SLOTS_PER_EPOCH),
    GENESIS_START_SHARD=Shard(0),
    BLS_WITHDRAWAL_PREFIX_BYTE=b'\x00',
    # Time parameters
    SECONDS_PER_SLOT=Second(6),  # seconds
    MIN_ATTESTATION_INCLUSION_DELAY=2**2,  # (= 4) slots
    SLOTS_PER_EPOCH=SLOTS_PER_EPOCH,  # (= 64) slots
    MIN_SEED_LOOKAHEAD=2**0,  # (= 1) epochs
    ACTIVATION_EXIT_DELAY=2**2,  # (= 4) epochs
    EPOCHS_PER_ETH1_VOTING_PERIOD=2**4,  # (= 16) epochs
    MIN_VALIDATOR_WITHDRAWABILITY_DELAY=2**8,  # (= 256) epochs
    PERSISTENT_COMMITTEE_PERIOD=2**11,  # (= 2,048) epochs
    # State list lengths
    SLOTS_PER_HISTORICAL_ROOT=2**13,  # (= 8,192) slots
    LATEST_ACTIVE_INDEX_ROOTS_LENGTH=2**13,  # (= 8,192) epochs
    LATEST_RANDAO_MIXES_LENGTH=2**13,  # (= 8,192) epochs
    LATEST_SLASHED_EXIT_LENGTH=2**13,  # (= 8,192) epochs
    # Reward and penalty quotients
    BASE_REWARD_QUOTIENT=2**10,  # (= 1,024)
    WHISTLEBLOWER_REWARD_QUOTIENT=2**9,  # (= 512)
    ATTESTATION_INCLUSION_REWARD_QUOTIENT=2**3,  # (= 8)
    INACTIVITY_PENALTY_QUOTIENT=2**24,  # (= 16,777,216)
    MIN_PENALTY_QUOTIENT=2**5,
    # Max operations per block
    MAX_PROPOSER_SLASHINGS=2**4,  # (= 16)
    MAX_ATTESTER_SLASHINGS=2**0,  # (= 1)
    MAX_ATTESTATIONS=2**7,  # (= 128)
    MAX_DEPOSITS=2**4,  # (= 16)
    MAX_VOLUNTARY_EXITS=2**4,  # (= 16)
    MAX_TRANSFERS=2**4,  # (= 16)
)
