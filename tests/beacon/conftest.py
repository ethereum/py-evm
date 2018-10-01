import pytest

from eth.beacon.config import (
    BASE_REWARD_QUOTIENT,
    DEFAULT_END_DYNASTY,
    DEPOSIT_SIZE,
    CYCLE_LENGTH,
    MAX_VALIDATOR_COUNT,
    MIN_COMMITTEE_SIZE,
    MIN_DYNASTY_LENGTH,
    SHARD_COUNT,
    SLOT_DURATION,
    SQRT_E_DROP_TIME,
    generate_config,
)
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
# config
#

@pytest.fixture
def init_shuffling_seed():
    return DEFAULT_SHUFFLING_SEED


@pytest.fixture
def init_randao():
    return DEFAULT_RANDAO


@pytest.fixture
def base_reward_quotient():
    return BASE_REWARD_QUOTIENT


@pytest.fixture
def default_end_dynasty():
    return DEFAULT_END_DYNASTY


@pytest.fixture
def deposit_size():
    return DEPOSIT_SIZE


@pytest.fixture
def cycle_length():
    return CYCLE_LENGTH


@pytest.fixture
def max_validator_count():
    return MAX_VALIDATOR_COUNT


@pytest.fixture
def min_committee_size():
    return MIN_COMMITTEE_SIZE


@pytest.fixture
def min_dynasty_length():
    return MIN_DYNASTY_LENGTH


@pytest.fixture
def shard_count():
    return SHARD_COUNT


@pytest.fixture
def slot_duration():
    return SLOT_DURATION


@pytest.fixture
def sqrt_e_drop_time():
    return SQRT_E_DROP_TIME


@pytest.fixture
def beacon_config(base_reward_quotient,
                  default_end_dynasty,
                  deposit_size,
                  cycle_length,
                  max_validator_count,
                  min_committee_size,
                  min_dynasty_length,
                  shard_count,
                  slot_duration,
                  sqrt_e_drop_time):
    return generate_config(
        base_reward_quotient=base_reward_quotient,
        default_end_dynasty=default_end_dynasty,
        deposit_size=deposit_size,
        cycle_length=cycle_length,
        max_validator_count=max_validator_count,
        min_committee_size=min_committee_size,
        min_dynasty_length=min_dynasty_length,
        shard_count=shard_count,
        slot_duration=slot_duration,
        sqrt_e_drop_time=sqrt_e_drop_time
    )
