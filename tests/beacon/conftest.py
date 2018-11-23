import pytest

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
def sample_attestation_record_params():
    return {
        'slot': 10,
        'shard': 12,
        'parent_hashes': [b'\x11' * 32],
        'shard_block_hash': b'\x22' * 32,
        'last_crosslink_hash': b'\x33' * 32,
        'shard_block_combined_data_root': b'\x44' * 32,
        'attester_bitfield': b'\x33\x1F',
        'justified_slot': 5,
        'justified_block_hash': b'\x33' * 32,
        'aggregate_sig': [0, 0],
    }


@pytest.fixture
def sample_beacon_block_params():
    return {
        'slot': 10,
        'randao_reveal': b'\x55' * 32,
        'candidate_pow_receipt_root': b'\x55' * 32,
        'ancestor_hashes': (),
        'state_root': b'\x55' * 32,
        'attestations': (),
        'specials': (),
        'proposer_signature': (),
    }


@pytest.fixture
def sample_beacon_state_params():
    return {
        'validator_set_change_slot': 10,
        'validators': (),
        'crosslinks': (),
        'last_state_recalculation_slot': 1,
        'last_finalized_slot': 2,
        'last_justified_slot': 2,
        'justified_streak': 2,
        'shard_and_committee_for_slots': (),
        'persistent_committees': (),
        'persistent_committee_reassignments': (),
        'next_shuffling_seed': b'\x55' * 32,
        'deposits_penalized_in_period': (),
        'validator_set_delta_hash_chain': b'\x55' * 32,
        'current_exit_seq': 10,
        'genesis_time': 10,
        'known_pow_receipt_root': b'\x55' * 32,
        'candidate_pow_receipt_root': b'\x55' * 32,
        'candidate_pow_receipt_root_votes': 5,
        'pre_fork_version': 0,
        'post_fork_version': 1,
        'fork_slot_number': 10,
        'pending_attestations': (),
        'recent_block_hashes': (),
        'randao_mix': b'\x55' * 32,
    }


@pytest.fixture
def sample_crosslink_record_params():
    return {
        'slot': 0,
        'shard_block_hash': b'\x43' * 32,
    }


@pytest.fixture
def sample_proposal_signed_data_params():
    return {
        'fork_version': 9,
        'slot': 10,
        'shard': 12,
        'block_hash': b'\x43' * 32,
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
        'shard': 10,
        'committee': (1, 3, 5),
    }


@pytest.fixture
def sample_shard_reassignment_record():
    return {
        'validator_index': 10,
        'shard': 11,
        'slot': 12,
    }


@pytest.fixture
def sample_special_params():
    return {
        'kind': 10,
        'data': b'\x55' * 100,
    }


@pytest.fixture
def sample_validator_record_params():
    return {
        'pubkey': 123,
        'withdrawal_shard': 10,
        'withdrawal_address': b'\x01' * 20,
        'randao_commitment': b'\x01' * 32,
        'randao_last_change': 1,
        'balance': 100,
        'status': 1,
        'exit_slot': 0,
        'exit_seq': 0
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
