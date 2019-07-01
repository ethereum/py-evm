from eth2.beacon.state_machines.forks.serenity.configs import (
    SERENITY_CONFIG,
)


XIAO_LONG_BAO_CONFIG = SERENITY_CONFIG._replace(
    SLOTS_PER_EPOCH=4,
    TARGET_COMMITTEE_SIZE=2,
    SHARD_COUNT=4,
    MIN_ATTESTATION_INCLUSION_DELAY=2,
    # Shorten the HISTORICAL lengths to make genesis yaml lighter
    EPOCHS_PER_HISTORICAL_VECTOR=2**7,
    SLOTS_PER_HISTORICAL_ROOT=2**4,
    EPOCHS_PER_SLASHED_BALANCES_VECTOR=2**4,
)
