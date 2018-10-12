import pytest

from eth.beacon.state_machines.configs import BeaconConfig


@pytest.fixture
def config(base_reward_quotient,
           default_end_dynasty,
           deposit_size,
           cycle_length,
           min_committee_size,
           min_dynasty_length,
           shard_count,
           slot_duration,
           sqrt_e_drop_time):
    return BeaconConfig(
        BASE_REWARD_QUOTIENT=base_reward_quotient,
        DEFAULT_END_DYNASTY=default_end_dynasty,
        DEPOSIT_SIZE=deposit_size,
        CYCLE_LENGTH=cycle_length,
        MIN_COMMITTEE_SIZE=min_committee_size,
        MIN_DYNASTY_LENGTH=min_dynasty_length,
        SHARD_COUNT=shard_count,
        SLOT_DURATION=slot_duration,
        SQRT_E_DROP_TIME=sqrt_e_drop_time,
    )
