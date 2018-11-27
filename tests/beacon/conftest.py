import pytest

from eth_utils import denoms
from eth_utils import (
    to_tuple,
)

from eth.constants import (
    ZERO_HASH32,
)
import eth.utils.bls as bls
from eth.utils.blake import blake

from eth.beacon.enums.validator_status_codes import (
    ValidatorStatusCode,
)
from eth.beacon.state_machines.forks.serenity.configs import SERENITY_CONFIG
from eth.beacon.types.validator_records import (
    ValidatorRecord,
)

from eth.beacon.types.attestation_signed_data import (
    AttestationSignedData,
)


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
def sample_attestation_record_params(sample_attestation_signed_data_params):
    return {
        'data': AttestationSignedData(**sample_attestation_signed_data_params),
        'attester_bitfield': b'\12' * 16,
        'poc_bitfield': b'\34' * 16,
        'aggregate_sig': [0, 0],
    }


@pytest.fixture
def sample_attestation_signed_data_params():
    return {
        'slot': 10,
        'shard': 12,
        'block_hash': b'\x11' * 32,
        'cycle_boundary_hash': b'\x22' * 32,
        'shard_block_hash': b'\x33' * 32,
        'last_crosslink_hash': b'\x44' * 32,
        'justified_slot': 5,
        'justified_block_hash': b'\x55' * 32,
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
        'proposer_signature': (0, 0),
    }


@pytest.fixture
def sample_beacon_state_params():
    return {
        'validator_set_change_slot': 10,
        'validators': (),
        'crosslinks': (),
        'last_state_recalculation_slot': 1,
        'last_finalized_slot': 2,
        'prev_cycle_justification_source': 2,
        'justification_source': 2,
        'justified_slot_bitfield': 2,
        'shard_and_committee_for_slots': (),
        'persistent_committees': (),
        'persistent_committee_reassignments': (),
        'next_shuffling_seed': b'\x55' * 32,
        'deposits_penalized_in_period': (),
        'validator_set_delta_hash_chain': b'\x55' * 32,
        'current_exit_seq': 10,
        'genesis_time': 10,
        'processed_pow_receipt_root': b'\x55' * 32,
        'candidate_pow_receipt_roots': (),
        'pre_fork_version': 0,
        'post_fork_version': 1,
        'fork_slot_number': 10,
        'pending_attestations': (),
        'recent_block_hashes': (),
        'randao_mix': b'\x55' * 32,
    }


@pytest.fixture
def sample_candidate_pow_receipt_root_record_params():
    return {
        'candidate_pow_receipt_root': b'\x43' * 32,
        'votes': 10,
    }


@pytest.fixture
def sample_crosslink_record_params():
    return {
        'slot': 0,
        'shard_block_hash': b'\x43' * 32,
    }


@pytest.fixture
def sample_fork_data_params():
    return {
        'pre_fork_version': 0,
        'post_fork_version': 0,
        'fork_slot_number': 2**64 - 1,
    }


@pytest.fixture
def sample_processed_attestation_params(sample_attestation_signed_data_params):
    return {
        'data': AttestationSignedData(**sample_attestation_signed_data_params),
        'attester_bitfield': b'\12' * 16,
        'poc_bitfield': b'\34' * 16,
        'slot_included': 0,
    }


@pytest.fixture
def sample_proposal_signed_data_params():
    return {
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
        'withdrawal_credentials': b'\x01' * 32,
        'randao_commitment': b'\x01' * 32,
        'randao_skips': 1,
        'balance': 100,
        'status': 1,
        'last_status_change_slot': 0,
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


#
# config
#
@pytest.fixture
def shard_count():
    return SERENITY_CONFIG.SHARD_COUNT


@pytest.fixture
def deposit_size():
    return SERENITY_CONFIG.DEPOSIT_SIZE


@pytest.fixture
def min_topup_size():
    return SERENITY_CONFIG.MIN_TOPUP_SIZE


@pytest.fixture
def min_online_deposit_size():
    return SERENITY_CONFIG.MIN_ONLINE_DEPOSIT_SIZE


@pytest.fixture
def deposit_contract_address():
    return SERENITY_CONFIG.DEPOSIT_CONTRACT_ADDRESS


@pytest.fixture
def deposits_for_chain_start():
    return SERENITY_CONFIG.DEPOSITS_FOR_CHAIN_START


@pytest.fixture
def target_committee_size():
    return SERENITY_CONFIG.TARGET_COMMITTEE_SIZE


@pytest.fixture
def genesis_time():
    return SERENITY_CONFIG.GENESIS_TIME


@pytest.fixture
def slot_duration():
    return SERENITY_CONFIG.SLOT_DURATION


@pytest.fixture
def cycle_length():
    return SERENITY_CONFIG.CYCLE_LENGTH


@pytest.fixture
def min_validator_set_change_interval():
    return SERENITY_CONFIG.MIN_VALIDATOR_SET_CHANGE_INTERVAL


@pytest.fixture
def shard_persistent_committee_change_period():
    return SERENITY_CONFIG.SHARD_PERSISTENT_COMMITTEE_CHANGE_PERIOD


@pytest.fixture
def min_attestation_inclusion_delay():
    return SERENITY_CONFIG.MIN_ATTESTATION_INCLUSION_DELAY


@pytest.fixture
def sqrt_e_drop_time():
    return SERENITY_CONFIG.SQRT_E_DROP_TIME


@pytest.fixture
def includer_reward_share_quotient():
    return SERENITY_CONFIG.INCLUDER_REWARD_SHARE_QUOTIENT


@pytest.fixture
def withdrawals_per_cycle():
    return SERENITY_CONFIG.WITHDRAWALS_PER_CYCLE


@pytest.fixture
def min_withdrawal_period():
    return SERENITY_CONFIG.MIN_WITHDRAWAL_PERIOD


@pytest.fixture
def deletion_period():
    return SERENITY_CONFIG.DELETION_PERIOD


@pytest.fixture
def collective_penalty_calculation_period():
    return SERENITY_CONFIG.COLLECTIVE_PENALTY_CALCULATION_PERIOD


@pytest.fixture
def pow_receipt_root_voting_period():
    return SERENITY_CONFIG.POW_RECEIPT_ROOT_VOTING_PERIOD


@pytest.fixture
def slashing_whistleblower_reward_denominator():
    return SERENITY_CONFIG.SLASHING_WHISTLEBLOWER_REWARD_DENOMINATOR


@pytest.fixture
def base_reward_quotient():
    return SERENITY_CONFIG.BASE_REWARD_QUOTIENT


@pytest.fixture
def max_validator_churn_quotient():
    return SERENITY_CONFIG.MAX_VALIDATOR_CHURN_QUOTIENT


@pytest.fixture
def pow_contract_merkle_tree_depth():
    return SERENITY_CONFIG.POW_CONTRACT_MERKLE_TREE_DEPTH


@pytest.fixture
def max_attestation_count():
    return SERENITY_CONFIG.MAX_ATTESTATION_COUNT


@pytest.fixture
def initial_fork_version():
    return SERENITY_CONFIG.INITIAL_FORK_VERSION


#
# genesis
#
@pytest.fixture
@to_tuple
def genesis_validators(init_validator_keys,
                       init_randao,
                       deposit_size):
    return [
        ValidatorRecord(
            pubkey=pub,
            withdrawal_credentials=ZERO_HASH32,
            randao_commitment=init_randao,
            randao_skips=0,
            balance=deposit_size * denoms.gwei,
            status=ValidatorStatusCode.ACTIVE,
            last_status_change_slot=0,
            exit_seq=0,
        ) for pub in init_validator_keys
    ]
