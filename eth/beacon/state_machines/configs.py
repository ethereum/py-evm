from typing import (
    NamedTuple,
)

BeaconConfig = NamedTuple(
    'BeaconConfig',
    (
        ('BASE_REWARD_QUOTIENT', int),
        ('DEFAULT_END_DYNASTY', int),
        ('DEPOSIT_SIZE', int),
        ('CYCLE_LENGTH', int),
        ('MIN_COMMITTEE_SIZE', int),
        ('MIN_DYNASTY_LENGTH', int),
        ('SHARD_COUNT', int),
        ('SLOT_DURATION', int),
        ('SQRT_E_DROP_TIME', int),
    )
)
