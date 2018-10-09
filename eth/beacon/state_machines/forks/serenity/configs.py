
from eth_utils import denoms
from eth.beacon.state_machines.configs import BeaconConfig


SERENITY_CONFIG = BeaconConfig(
    BASE_REWARD_QUOTIENT=2**15,
    DEFAULT_END_DYNASTY=9999999999999999999,
    DEPOSIT_SIZE=32 * denoms.ether,  # WEI
    CYCLE_LENGTH=64,  # slots
    MIN_COMMITTEE_SIZE=128,  # validators
    MIN_DYNASTY_LENGTH=256,  # slots
    SHARD_COUNT=1024,  # shards
    SLOT_DURATION=8,  # seconds
    SQRT_E_DROP_TIME=2**20,  # seconds
)
