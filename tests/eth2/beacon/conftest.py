import pytest
import rlp

from eth.constants import (
    ZERO_HASH32,
)
from eth_utils import (
    to_tuple,
)

import eth2._utils.bls as bls
from eth2.beacon._utils.hash import hash_eth2
from eth2._utils.bitfield import (
    get_empty_bitfield,
)
from eth2.beacon.aggregation import (
    aggregate_votes,
)
from eth2.beacon.constants import (
    FAR_FUTURE_SLOT,
    GWEI_PER_ETH,
)
from eth2.beacon.enums import (
    SignatureDomain,
)
from eth2.beacon.helpers import (
    get_domain,
)

from eth2.beacon.helpers import (
    get_shuffling,
)
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.states import BeaconState
from eth2.beacon.types.crosslink_records import CrosslinkRecord
from eth2.beacon.types.deposit_data import DepositData
from eth2.beacon.types.deposit_input import DepositInput
from eth2.beacon.types.eth1_data import Eth1Data
from eth2.beacon.types.proposal_signed_data import ProposalSignedData
from eth2.beacon.types.slashable_vote_data import SlashableVoteData

from eth2.beacon.types.blocks import (
    BeaconBlockBody,
)
from eth2.beacon.state_machines.forks.serenity.configs import SERENITY_CONFIG
from eth2.beacon.types.fork_data import (
    ForkData,
)

from tests.eth2.beacon.helpers import (
    mock_validator_record,
)

DEFAULT_SHUFFLING_SEED = b'\00' * 32
DEFAULT_RANDAO = b'\45' * 32
DEFAULT_NUM_VALIDATORS = 40


@pytest.fixture(scope="session")
def privkeys():
    return [int.from_bytes(hash_eth2(str(i).encode('utf-8'))[:4], 'big') for i in range(100)]


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
def sample_proposer_slashing_params(sample_proposal_signed_data_params):
    proposal_data = ProposalSignedData(**sample_proposal_signed_data_params)
    return {
        'proposer_index': 1,
        'proposal_data_1': proposal_data,
        'proposal_signature_1': (1, 2, 3),
        'proposal_data_2': proposal_data,
        'proposal_signature_2': (4, 5, 6),
    }


@pytest.fixture
def sample_attestation_params(sample_attestation_data_params):
    return {
        'data': AttestationData(**sample_attestation_data_params),
        'participation_bitfield': b'\12' * 16,
        'custody_bitfield': b'\34' * 16,
        'aggregate_signature': [0, 0],
    }


@pytest.fixture
def sample_attestation_data_params():
    return {
        'slot': 10,
        'shard': 12,
        'beacon_block_root': b'\x11' * 32,
        'epoch_boundary_root': b'\x22' * 32,
        'shard_block_root': b'\x33' * 32,
        'latest_crosslink_root': b'\x44' * 32,
        'justified_slot': 5,
        'justified_block_root': b'\x55' * 32,
    }


@pytest.fixture
def sample_attestation_data_and_custody_bit_params(sample_attestation_data_params):
    return {
        'data': AttestationData(**sample_attestation_data_params),
        'custody_bit': False,
    }


@pytest.fixture
def sample_beacon_block_body_params():
    return {
        'proposer_slashings': (),
        'casper_slashings': (),
        'attestations': (),
        'custody_reseeds': (),
        'custody_challenges': (),
        'custody_responses': (),
        'deposits': (),
        'exits': (),
    }


@pytest.fixture
def sample_beacon_block_params(sample_beacon_block_body_params,
                               sample_eth1_data_params):
    return {
        'slot': 10,
        'parent_root': ZERO_HASH32,
        'state_root': b'\x55' * 32,
        'randao_reveal': b'\x55' * 32,
        'eth1_data': Eth1Data(**sample_eth1_data_params),
        'signature': (0, 0),
        'body': BeaconBlockBody(**sample_beacon_block_body_params)
    }


@pytest.fixture
def sample_beacon_state_params(sample_fork_data_params, sample_eth1_data_params):
    return {
        'slot': 0,
        'genesis_time': 0,
        'fork_data': ForkData(**sample_fork_data_params),
        'validator_registry': (),
        'validator_balances': (),
        'validator_registry_latest_change_slot': 10,
        'validator_registry_exit_count': 10,
        'validator_registry_delta_chain_tip': b'\x55' * 32,
        'latest_randao_mixes': (),
        'latest_vdf_outputs': (),
        'crosslink_committees_at_slots': (),
        'persistent_committees': (),
        'persistent_committee_reassignments': (),
        'custody_challenges': (),
        'previous_justified_slot': 0,
        'justified_slot': 0,
        'justification_bitfield': b'\x00',
        'finalized_slot': 0,
        'latest_crosslinks': (),
        'latest_block_roots': (),
        'latest_penalized_exit_balances': (),
        'latest_attestations': (),
        'batched_block_roots': (),
        'latest_eth1_data': Eth1Data(**sample_eth1_data_params),
        'eth1_data_votes': (),
    }


@pytest.fixture
def sample_eth1_data_params():
    return {
        'deposit_root': b'\x43' * 32,
        'block_hash': b'\x46' * 32,
    }


@pytest.fixture
def sample_eth1_data_vote_params(sample_eth1_data_params):
    return {
        'eth1_data': Eth1Data(**sample_eth1_data_params),
        'vote_count': 10,
    }


@pytest.fixture
def sample_crosslink_record_params():
    return {
        'slot': 0,
        'shard_block_root': b'\x43' * 32,
    }


@pytest.fixture
def sample_deposit_input_params():
    return {
        'pubkey': 123,
        'withdrawal_credentials': b'\11' * 32,
        'randao_commitment': b'\11' * 32,
        'custody_commitment': ZERO_HASH32,
        'proof_of_possession': (0, 0),
    }


@pytest.fixture
def sample_deposit_data_params(sample_deposit_input_params):
    return {
        'deposit_input': DepositInput(**sample_deposit_input_params),
        'amount': 56,
        'timestamp': 1501851927,
    }


@pytest.fixture
def sample_deposit_params(sample_deposit_data_params):
    return {
        'merkle_branch': (),
        'merkle_tree_index': 5,
        'deposit_data': DepositData(**sample_deposit_data_params)
    }


@pytest.fixture
def sample_exit_params():
    return {
        'slot': 123,
        'validator_index': 15,
        'signature': (0, 0),
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
        'block_root': b'\x43' * 32,
    }


@pytest.fixture
def sample_recent_proposer_record_params():
    return {
        'index': 10,
        'randao_commitment': b'\x43' * 32,
        'balance_delta': 3
    }


@pytest.fixture
def sample_crosslink_committee_params():
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
def sample_slashable_vote_data_params(sample_attestation_data_params):
    return {
        'custody_bit_0_indices': (10, 11, 12, 15, 28),
        'custody_bit_1_indices': (7, 8, 100, 131, 249),
        'data': AttestationData(**sample_attestation_data_params),
        'aggregate_signature': (1, 2, 3, 4, 5),
    }


@pytest.fixture
def sample_casper_slashing_params(sample_slashable_vote_data_params):
    vote_data = SlashableVoteData(**sample_slashable_vote_data_params)
    return {
        'slashable_vote_data_1': vote_data,
        'slashable_vote_data_2': vote_data,
    }


@pytest.fixture
def sample_validator_record_params():
    return {
        'pubkey': 123,
        'withdrawal_credentials': b'\x01' * 32,
        'randao_commitment': b'\x01' * 32,
        'randao_layers': 1,
        'activation_slot': FAR_FUTURE_SLOT,
        'exit_slot': FAR_FUTURE_SLOT,
        'withdrawal_slot': FAR_FUTURE_SLOT,
        'penalized_slot': FAR_FUTURE_SLOT,
        'exit_count': 0,
        'status_flags': 0,
        'custody_commitment': ZERO_HASH32,
        'latest_custody_reseed_slot': 0,
        'penultimate_custody_reseed_slot': 0,
    }


@pytest.fixture
def sample_validator_registry_delta_block_params():
    return {
        'latest_registry_delta_root': b'\x01' * 32,
        'validator_index': 1,
        'pubkey': 123,
        'slot': 0,
        'flag': 1,
    }


@pytest.fixture
def empty_beacon_state(latest_block_roots_length,
                       latest_penalized_exit_length,
                       sample_eth1_data_params):
    return BeaconState(
        slot=0,
        genesis_time=0,
        fork_data=ForkData(
            pre_fork_version=0,
            post_fork_version=0,
            fork_slot=0,
        ),
        validator_registry=(),
        validator_balances=(),
        validator_registry_latest_change_slot=10,
        validator_registry_exit_count=0,
        validator_registry_delta_chain_tip=ZERO_HASH32,
        latest_randao_mixes=(),
        latest_vdf_outputs=(),
        crosslink_committees_at_slots=(),
        persistent_committees=(),
        persistent_committee_reassignments=(),
        previous_justified_slot=0,
        justified_slot=0,
        justification_bitfield=0,
        finalized_slot=0,
        latest_crosslinks=(),
        latest_block_roots=(ZERO_HASH32,) * latest_block_roots_length,
        latest_penalized_exit_balances=(0,) * latest_penalized_exit_length,
        latest_attestations=(),
        batched_block_roots=(),
        latest_eth1_data=Eth1Data(**sample_eth1_data_params),
        eth1_data_votes=(),
    )


@pytest.fixture()
def ten_validators_state(empty_beacon_state, max_deposit):
    validator_count = 10
    return empty_beacon_state.copy(
        validator_registry=tuple(
            mock_validator_record(
                pubkey=pubkey,
                is_active=True,
            )
            for pubkey in range(validator_count)
        ),
        validator_balances=(max_deposit * GWEI_PER_ETH,) * validator_count,
    )


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
def init_validator_privkeys(privkeys, num_validators):
    return privkeys[:num_validators]


@pytest.fixture
def init_validator_pubkeys(pubkeys, num_validators):
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
def ejection_balance():
    return SERENITY_CONFIG.EJECTION_BALANCE


@pytest.fixture
def max_balance_churn_quotient():
    return SERENITY_CONFIG.MAX_BALANCE_CHURN_QUOTIENT


@pytest.fixture
def beacon_chain_shard_number():
    return SERENITY_CONFIG.BEACON_CHAIN_SHARD_NUMBER


@pytest.fixture
def max_casper_votes():
    return SERENITY_CONFIG.MAX_CASPER_VOTES


@pytest.fixture
def latest_block_roots_length():
    return SERENITY_CONFIG.LATEST_BLOCK_ROOTS_LENGTH


@pytest.fixture
def latest_randao_mixes_length():
    return SERENITY_CONFIG.LATEST_RANDAO_MIXES_LENGTH


@pytest.fixture
def latest_penalized_exit_length():
    return SERENITY_CONFIG.LATEST_PENALIZED_EXIT_LENGTH


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
def genesis_fork_version():
    return SERENITY_CONFIG.GENESIS_FORK_VERSION


@pytest.fixture
def genesis_slot():
    return SERENITY_CONFIG.GENESIS_SLOT


@pytest.fixture
def bls_withdrawal_prefix_byte():
    return SERENITY_CONFIG.BLS_WITHDRAWAL_PREFIX_BYTE


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
def seed_lookahead():
    return SERENITY_CONFIG.SEED_LOOKAHEAD


@pytest.fixture
def entry_exit_delay():
    return SERENITY_CONFIG.ENTRY_EXIT_DELAY


@pytest.fixture
def eth1_data_voting_period():
    return SERENITY_CONFIG.ETH1_DATA_VOTING_PERIOD


@pytest.fixture
def min_validator_withdrawal_time():
    return SERENITY_CONFIG.MIN_VALIDATOR_WITHDRAWAL_TIME


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


@pytest.fixture
def max_proposer_slashings():
    return SERENITY_CONFIG.MAX_PROPOSER_SLASHINGS


@pytest.fixture
def max_casper_slashings():
    return SERENITY_CONFIG.MAX_CASPER_SLASHINGS


@pytest.fixture
def max_attestations():
    return SERENITY_CONFIG.MAX_ATTESTATIONS


@pytest.fixture
def max_deposits():
    return SERENITY_CONFIG.MAX_DEPOSITS


@pytest.fixture
def max_exits():
    return SERENITY_CONFIG.MAX_EXITS


#
# genesis
#
@pytest.fixture
def genesis_state(sample_beacon_state_params,
                  activated_genesis_validators,
                  genesis_balances,
                  epoch_length,
                  target_committee_size,
                  genesis_slot,
                  shard_count,
                  latest_block_roots_length):
    initial_shuffling = get_shuffling(
        seed=ZERO_HASH32,
        validators=activated_genesis_validators,
        crosslinking_start_shard=0,
        slot=genesis_slot,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count
    )
    return BeaconState(**sample_beacon_state_params).copy(
        validator_registry=activated_genesis_validators,
        validator_balances=genesis_balances,
        crosslink_committees_at_slots=initial_shuffling + initial_shuffling,
        latest_block_roots=tuple(ZERO_HASH32 for _ in range(latest_block_roots_length)),
        latest_crosslinks=tuple(
            CrosslinkRecord(
                slot=genesis_slot,
                shard_block_root=ZERO_HASH32,
            )
            for _ in range(shard_count)
        )
    )


@pytest.fixture
def initial_validators(init_validator_pubkeys,
                       init_randao,
                       max_deposit):
    """
    Inactive
    """
    return tuple(
        mock_validator_record(
            pubkey=pubkey,
            withdrawal_credentials=ZERO_HASH32,
            randao_commitment=init_randao,
            status_flags=0,
            is_active=False,
        )
        for pubkey in init_validator_pubkeys
    )


@to_tuple
@pytest.fixture
def activated_genesis_validators(initial_validators, genesis_slot):
    """
    Active
    """
    for validator in initial_validators:
        yield validator.copy(activation_slot=genesis_slot)


@pytest.fixture
def genesis_balances(init_validator_pubkeys, max_deposit):
    return tuple(
        max_deposit * GWEI_PER_ETH
        for _ in init_validator_pubkeys
    )


#
# Create mock consensus objects
#
@pytest.fixture
def create_mock_signed_attestation(privkeys):
    def create_mock_signed_attestation(state,
                                       crosslink_committee,
                                       voting_committee_indices,
                                       attestation_data):
        message = hash_eth2(
            rlp.encode(attestation_data) +
            (0).to_bytes(1, "big")
        )
        # participants sign message
        signatures = [
            bls.sign(
                message,
                privkeys[crosslink_committee.committee[committee_index]],
                domain=get_domain(
                    fork_data=state.fork_data,
                    slot=attestation_data.slot,
                    domain_type=SignatureDomain.DOMAIN_ATTESTATION,
                )
            )
            for committee_index in voting_committee_indices
        ]

        # aggregate signatures and construct participant bitfield
        participation_bitfield, aggregate_signature = aggregate_votes(
            bitfield=get_empty_bitfield(len(crosslink_committee.committee)),
            sigs=(),
            voting_sigs=signatures,
            voting_committee_indices=voting_committee_indices,
        )

        # create attestation from attestation_data, particpipant_bitfield, and signature
        return Attestation(
            data=attestation_data,
            participation_bitfield=participation_bitfield,
            custody_bitfield=b'',
            aggregate_signature=aggregate_signature,
        )

    return create_mock_signed_attestation
