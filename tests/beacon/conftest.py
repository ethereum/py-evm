import pytest

from eth_utils import (
    to_tuple,
)

from eth.beacon.db.chain import BeaconChainDB
from eth.beacon.genesis_helpers import (
    get_genesis_active_state,
    get_genesis_block,
    get_genesis_crystallized_state,
)
from eth.beacon.state_machines.configs import BeaconConfig
from eth.beacon.state_machines.forks.serenity import SerenityStateMachine
from eth.beacon.state_machines.forks.serenity.configs import SERENITY_CONFIG

from eth.beacon.types.validator_records import ValidatorRecord
import eth.utils.bls as bls
from eth.utils.blake import blake


DEFAULT_SHUFFLING_SEED = b'\00' * 32
DEFAULT_RANDAO = b'\45' * 32
DEFAULT_NUM_VALIDATORS = 40


@pytest.fixture(scope="session")
def privkeys():
    return [int.from_bytes(blake(str(i).encode('utf-8'))[:4], 'big') for i in range(1000)]


@pytest.fixture(scope="session")
def keymap(privkeys):
    keymap = {}
    for i, k in enumerate(privkeys):
        keymap[bls.privtopub(k)] = k
        if i % 50 == 0:
            print("Generated %d keys" % i)
    return keymap


@pytest.fixture(scope="session")
def pubkeys(keymap):
    return list(keymap)


@pytest.fixture
def sample_active_state_params():
    return {
        'pending_attestations': [],
        'recent_block_hashes': [],
    }


@pytest.fixture
def sample_attestation_record_params():
    return {
        'slot': 10,
        'shard_id': 12,
        'oblique_parent_hashes': [],
        'shard_block_hash': b'\x20' * 32,
        'attester_bitfield': b'\x33\x1F',
        'justified_slot': 5,
        'justified_block_hash': b'\x33' * 32,
        'aggregate_sig': [0, 0],
    }


@pytest.fixture
def sample_block_params():
    return {
        'parent_hash': b'\x55' * 32,
        'slot_number': 10,
        'randao_reveal': b'\x34' * 32,
        'attestations': [],
        'pow_chain_ref': b'\x32' * 32,
        'active_state_root': b'\x01' * 32,
        'crystallized_state_root': b'\x05' * 32
    }


@pytest.fixture
def sample_crystallized_state_params():
    return {
        'validators': [],
        'last_state_recalc': 50,
        'shard_and_committee_for_slots': [],
        'last_justified_slot': 100,
        'justified_streak': 10,
        'last_finalized_slot': 70,
        'current_dynasty': 4,
        'crosslink_records': [],
        'dynasty_seed': b'\x55' * 32,
        'dynasty_start': 3,
    }


@pytest.fixture
def sample_crosslink_record_params():
    return {
        'dynasty': 2,
        'slot': 0,
        'hash': b'\x43' * 32,
    }


@pytest.fixture
def sample_recent_proposer_record_params():
    return {
        'index': 10,
        'randao_commitment': b'\x43' * 32,
        'balance_delta': 3
    }


@pytest.fixture
def sample_shard_and_committee_params():
    return {
        'shard_id': 10,
        'committee': [],
    }


@pytest.fixture
def sample_validator_record_params():
    return {
        'pubkey': 123,
        'withdrawal_shard': 10,
        'withdrawal_address': b'\x01' * 20,
        'randao_commitment': b'\x01' * 32,
        'balance': 100,
        'start_dynasty': 1,
        'end_dynasty': 3
    }


#
# Temporary default values
#
@pytest.fixture
def init_shuffling_seed():
    return DEFAULT_SHUFFLING_SEED


@pytest.fixture
def init_randao():
    return DEFAULT_RANDAO


@pytest.fixture
def num_validators():
    return DEFAULT_NUM_VALIDATORS


@pytest.fixture
def init_validator_keys(pubkeys, num_validators):
    return pubkeys[:num_validators]


#
# config
#
@pytest.fixture
def base_reward_quotient():
    return SERENITY_CONFIG.BASE_REWARD_QUOTIENT


@pytest.fixture
def default_end_dynasty():
    return SERENITY_CONFIG.DEFAULT_END_DYNASTY


@pytest.fixture
def deposit_size():
    return SERENITY_CONFIG.DEPOSIT_SIZE


@pytest.fixture
def cycle_length():
    return SERENITY_CONFIG.CYCLE_LENGTH


@pytest.fixture
def min_committee_size():
    return SERENITY_CONFIG.MIN_COMMITTEE_SIZE


@pytest.fixture
def min_dynasty_length():
    return SERENITY_CONFIG.MIN_DYNASTY_LENGTH


@pytest.fixture
def shard_count():
    return SERENITY_CONFIG.SHARD_COUNT


@pytest.fixture
def slot_duration():
    return SERENITY_CONFIG.SLOT_DURATION


@pytest.fixture
def sqrt_e_drop_time():
    return SERENITY_CONFIG.SQRT_E_DROP_TIME


#
# genesis
#
@pytest.fixture
@to_tuple
def genesis_validators(init_validator_keys,
                       init_randao,
                       deposit_size,
                       default_end_dynasty):
    current_dynasty = 1
    return [
        ValidatorRecord(
            pubkey=pub,
            withdrawal_shard=0,
            withdrawal_address=blake(pub.to_bytes(32, 'big'))[-20:],
            randao_commitment=init_randao,
            balance=deposit_size,
            start_dynasty=current_dynasty,
            end_dynasty=default_end_dynasty
        ) for pub in init_validator_keys
    ]


@pytest.fixture
def genesis_crystallized_state(genesis_validators,
                               init_shuffling_seed,
                               cycle_length,
                               min_committee_size,
                               shard_count):
    return get_genesis_crystallized_state(
        genesis_validators,
        init_shuffling_seed,
        cycle_length,
        min_committee_size,
        shard_count,
    )


@pytest.fixture
def genesis_active_state(cycle_length):
    return get_genesis_active_state(cycle_length)


@pytest.fixture
def genesis_block(genesis_active_state, genesis_crystallized_state):
    active_state_root = genesis_active_state.hash
    crystallized_state_root = genesis_crystallized_state.hash

    return get_genesis_block(
        active_state_root=active_state_root,
        crystallized_state_root=crystallized_state_root,
    )


#
# State Machine
#
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
    return SerenityStateMachine.configure(
        __name__='SerenityStateMachineForTesting',
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
