import pytest

from eth_utils import denoms

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

from eth.beacon.types.attestation_data import (
    AttestationData,
)

from eth.beacon.types.fork_data import (
    ForkData,
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
def sample_attestation_record_params(sample_attestation_data_params):
    return {
        'data': AttestationData(**sample_attestation_data_params),
        'participation_bitfield': b'\12' * 16,
        'custody_bitfield': b'\34' * 16,
        'aggregate_sig': [0, 0],
    }


@pytest.fixture
def sample_attestation_data_params():
    return {
        'slot': 10,
        'shard': 12,
        'beacon_block_hash': b'\x11' * 32,
        'epoch_boundary_hash': b'\x22' * 32,
        'shard_block_hash': b'\x33' * 32,
        'latest_crosslink_hash': b'\x44' * 32,
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
def sample_beacon_state_params(sample_fork_data_params):
    return {
        'validator_registry': (),
        'validator_registry_latest_change_slot': 10,
        'validator_registry_exit_count': 10,
        'validator_registry_delta_chain_tip': b'\x55' * 32,
        'randao_mix': b'\x55' * 32,
        'next_seed': b'\x55' * 32,
        'shard_committees_at_slots': (),
        'persistent_committees': (),
        'persistent_committee_reassignments': (),
        'previous_justified_slot': 0,
        'justified_slot': 0,
        'justification_bitfield': 0,
        'finalized_slot': 0,
        'latest_crosslinks': (),
        'latest_state_recalculation_slot': 0,
        'latest_block_hashes': (),
        'latest_penalized_exit_balances': (),
        'latest_attestations': (),
        'processed_pow_receipt_root': b'\x55' * 32,
        'candidate_pow_receipt_roots': (),
        'genesis_time': 0,
        'fork_data': ForkData(**sample_fork_data_params),
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
def sample_deposit_parameters_records_params():
    return {
        # BLS pubkey
        'pubkey': 123,
        # BLS proof of possession (a BLS signature)
        'proof_of_possession': (0, 0),
        # Withdrawal credentials
        'withdrawal_credentials': b'\11' * 32,
        # Initial RANDAO commitment
        'randao_commitment': b'\11' * 32,
    }


@pytest.fixture
def sample_fork_data_params():
    return {
        'pre_fork_version': 0,
        'post_fork_version': 0,
        'fork_slot': 2**64 - 1,
    }


@pytest.fixture
def sample_pending_attestation_record_params(sample_attestation_data_params):
    return {
        'data': AttestationData(**sample_attestation_data_params),
        'participation_bitfield': b'\12' * 16,
        'custody_bitfield': b'\34' * 16,
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
def sample_shard_committee_params():
    return {
        'shard': 10,
        'committee': (1, 3, 5),
        'total_validator_count': 100
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
        'latest_status_change_slot': 0,
        'exit_count': 0
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
def target_committee_size():
    return SERENITY_CONFIG.TARGET_COMMITTEE_SIZE


@pytest.fixture
def max_attestations_per_block():
    return SERENITY_CONFIG.MAX_ATTESTATIONS_PER_BLOCK


@pytest.fixture
def min_balance():
    return SERENITY_CONFIG.MIN_BALANCE


@pytest.fixture
def max_balance_churn_quotient():
    return SERENITY_CONFIG.MAX_BALANCE_CHURN_QUOTIENT


@pytest.fixture
def gwei_per_eth():
    return SERENITY_CONFIG.GWEI_PER_ETH


@pytest.fixture
def beacon_chain_shard_number():
    return SERENITY_CONFIG.BEACON_CHAIN_SHARD_NUMBER


@pytest.fixture
def bls_withdrawal_credentials():
    return SERENITY_CONFIG.BLS_WITHDRAWAL_CREDENTIALS


@pytest.fixture
def deposit_contract_address():
    return SERENITY_CONFIG.DEPOSIT_CONTRACT_ADDRESS


@pytest.fixture
def deposit_contract_tree_depth():
    return SERENITY_CONFIG.DEPOSIT_CONTRACT_TREE_DEPTH


@pytest.fixture
def min_deposit():
    return SERENITY_CONFIG.MIN_DEPOSIT


@pytest.fixture
def max_deposit():
    return SERENITY_CONFIG.MAX_DEPOSIT


@pytest.fixture
def slot_duration():
    return SERENITY_CONFIG.SLOT_DURATION


@pytest.fixture
def min_attestation_inclusion_delay():
    return SERENITY_CONFIG.MIN_ATTESTATION_INCLUSION_DELAY


@pytest.fixture
def epoch_length():
    return SERENITY_CONFIG.EPOCH_LENGTH


@pytest.fixture
def min_validator_registry_change_interval():
    return SERENITY_CONFIG.MIN_VALIDATOR_REGISTRY_CHANGE_INTERVAL


@pytest.fixture
def pow_receipt_root_voting_period():
    return SERENITY_CONFIG.POW_RECEIPT_ROOT_VOTING_PERIOD


@pytest.fixture
def shard_persistent_committee_change_period():
    return SERENITY_CONFIG.SHARD_PERSISTENT_COMMITTEE_CHANGE_PERIOD


@pytest.fixture
def collective_penalty_calculation_period():
    return SERENITY_CONFIG.COLLECTIVE_PENALTY_CALCULATION_PERIOD


@pytest.fixture
def zero_balance_validator_ttl():
    return SERENITY_CONFIG.ZERO_BALANCE_VALIDATOR_TTL


@pytest.fixture
def base_reward_quotient():
    return SERENITY_CONFIG.BASE_REWARD_QUOTIENT


@pytest.fixture
def whistleblower_reward_quotient():
    return SERENITY_CONFIG.WHISTLEBLOWER_REWARD_QUOTIENT


@pytest.fixture
def includer_reward_quotient():
    return SERENITY_CONFIG.INCLUDER_REWARD_QUOTIENT


@pytest.fixture
def inactivity_penalty_quotient():
    return SERENITY_CONFIG.INACTIVITY_PENALTY_QUOTIENT


#
# genesis
#
@pytest.fixture
def genesis_validators(init_validator_keys,
                       init_randao,
                       max_deposit):
    return tuple(
        ValidatorRecord(
            pubkey=pub,
            withdrawal_credentials=ZERO_HASH32,
            randao_commitment=init_randao,
            randao_skips=0,
            balance=max_deposit * denoms.gwei,
            status=ValidatorStatusCode.ACTIVE,
            latest_status_change_slot=0,
            exit_count=0,
        ) for pub in init_validator_keys
    )
