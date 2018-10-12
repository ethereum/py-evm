import pytest

from eth.beacon.db.chain import BeaconChainDB
from eth.beacon.state_machines.configs import BeaconConfig
from eth.beacon.state_machines.forks.serenity import (
    SerenityBeaconStateMachine,
)


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


@pytest.fixture
def fixture_sm_class(config):
    return SerenityBeaconStateMachine.configure(
        __name__='SerenityBeaconStateMachineForTesting',
        config=config,
    )


@pytest.fixture
def initial_chaindb(base_db,
                    genesis_block,
                    genesis_crystallized_state,
                    genesis_active_state):
    chaindb = BeaconChainDB(base_db)
    chaindb.persist_block(genesis_block)
    chaindb.persist_crystallized_state(genesis_crystallized_state)
    chaindb.persist_active_state(genesis_active_state, genesis_crystallized_state.hash)
    return chaindb
