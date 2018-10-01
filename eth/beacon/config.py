from collections import (
    namedtuple,
)

from eth_utils import denoms

BASE_REWARD_QUOTIENT = 2**15
DEFAULT_END_DYNASTY = 9999999999999999999
DEPOSIT_SIZE = 32 * denoms.ether  # WEI
CYCLE_LENGTH = 64  # slots
MAX_VALIDATOR_COUNT = 2**22  # validators
MIN_COMMITTEE_SIZE = 128  # validators
MIN_DYNASTY_LENGTH = 256  # slots
SHARD_COUNT = 1024  # shards
SLOT_DURATION = 8  # seconds
SQRT_E_DROP_TIME = 2**20  # seconds

# Make sure quadratic_penalty_quotient is integer computation
assert SQRT_E_DROP_TIME % SLOT_DURATION == 0


BeaconConfig = namedtuple(
    'BeaconConfig',
    [
        'base_reward_quotient',
        'default_end_dynasty',
        'deposit_size',
        'cycle_length',
        'max_validator_count',
        'min_committee_size',
        'min_dynasty_length',
        'shard_count',
        'slot_duration',
        'sqrt_e_drop_time',
    ]
)


def generate_config(*,
                    base_reward_quotient: int=BASE_REWARD_QUOTIENT,
                    default_end_dynasty: int=DEFAULT_END_DYNASTY,
                    deposit_size: int=DEPOSIT_SIZE,
                    cycle_length: int=CYCLE_LENGTH,
                    max_validator_count: int=MAX_VALIDATOR_COUNT,
                    min_committee_size: int=MIN_COMMITTEE_SIZE,
                    min_dynasty_length: int=MIN_DYNASTY_LENGTH,
                    shard_count: int=SHARD_COUNT,
                    slot_duration: int=SLOT_DURATION,
                    sqrt_e_drop_time: int=SQRT_E_DROP_TIME) -> BeaconConfig:

    return BeaconConfig(
        base_reward_quotient=BASE_REWARD_QUOTIENT,
        default_end_dynasty=DEFAULT_END_DYNASTY,
        deposit_size=DEPOSIT_SIZE,
        cycle_length=CYCLE_LENGTH,
        max_validator_count=MAX_VALIDATOR_COUNT,
        min_committee_size=MIN_COMMITTEE_SIZE,
        min_dynasty_length=MIN_DYNASTY_LENGTH,
        shard_count=SHARD_COUNT,
        slot_duration=SLOT_DURATION,
        sqrt_e_drop_time=SQRT_E_DROP_TIME
    )


DEFAULT_CONFIG = generate_config()
