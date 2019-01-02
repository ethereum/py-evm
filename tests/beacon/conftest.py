import pytest
import rlp

from eth.constants import (
    ZERO_HASH32,
)

import eth._utils.bls as bls
from eth.beacon._utils.hash import hash_eth2
from eth._utils.bitfield import (
    get_empty_bitfield,
)
from eth.beacon.aggregation import (
    aggregate_votes,
)
from eth.beacon.constants import (
    EMPTY_SIGNATURE,
)
from eth.beacon.enums import (
    SignatureDomain,
)
from eth.beacon.helpers import (
    get_domain,
)

from eth.beacon.helpers import (
    get_new_shuffling,
)

from eth.beacon.types.proposal_signed_data import (
    ProposalSignedData,
)

from eth.beacon.types.slashable_vote_data import (
    SlashableVoteData,
)

from eth.beacon.types.attestation_data import AttestationData
from eth.beacon.types.attestations import Attestation
from eth.beacon.types.states import BeaconState
from eth.beacon.types.crosslink_records import CrosslinkRecord
from eth.beacon.types.deposits import DepositData
from eth.beacon.types.deposit_input import DepositInput

from eth.beacon.types.blocks import (
    BeaconBlock,
    BeaconBlockBody,
)

from eth.beacon.enums import (
    ValidatorStatusCode,
)

from eth.beacon.state_machines.configs import BeaconConfig
from eth.beacon.state_machines.forks.serenity import (
    SerenityStateMachine,
)
from eth.beacon.state_machines.forks.serenity.configs import SERENITY_CONFIG
from eth.beacon.types.validator_records import (
    ValidatorRecord,
)

from eth.beacon.types.fork_data import (
    ForkData,
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
def sample_beacon_block_body_params():
    return {
        'proposer_slashings': (),
        'casper_slashings': (),
        'attestations': (),
        'deposits': (),
        'exits': (),
    }


@pytest.fixture
def sample_beacon_block_params(sample_beacon_block_body_params):
    return {
        'slot': 10,
        'parent_root': ZERO_HASH32,
        'state_root': b'\x55' * 32,
        'randao_reveal': b'\x55' * 32,
        'candidate_pow_receipt_root': b'\x55' * 32,
        'signature': (0, 0),
        'body': BeaconBlockBody(**sample_beacon_block_body_params)
    }


@pytest.fixture
def sample_beacon_state_params(sample_fork_data_params):
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
        'shard_committees_at_slots': (),
        'persistent_committees': (),
        'persistent_committee_reassignments': (),
        'previous_justified_slot': 0,
        'justified_slot': 0,
        'justification_bitfield': b'\x00',
        'finalized_slot': 0,
        'latest_crosslinks': (),
        'latest_block_roots': (),
        'latest_penalized_exit_balances': (),
        'latest_attestations': (),
        'batched_block_roots': (),
        'processed_pow_receipt_root': b'\x55' * 32,
        'candidate_pow_receipt_roots': (),
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
        'shard_block_root': b'\x43' * 32,
    }


@pytest.fixture
def sample_deposit_input_params():
    return {
        'pubkey': 123,
        'proof_of_possession': (0, 0),
        'withdrawal_credentials': b'\11' * 32,
        'randao_commitment': b'\11' * 32,
    }


@pytest.fixture
def sample_deposit_data_params(sample_deposit_input_params):
    return {
        'deposit_input': DepositInput(**sample_deposit_input_params),
        'value': 56,
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
def sample_slashable_vote_data_params(sample_attestation_data_params):
    return {
        'aggregate_signature_poc_0_indices': (10, 11, 12, 15, 28),
        'aggregate_signature_poc_1_indices': (7, 8, 100, 131, 249),
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
        'status': 1,
        'latest_status_change_slot': 0,
        'exit_count': 0
    }


@pytest.fixture
def sample_validator_registry_delta_block_params():
    return {
        'latest_registry_delta_root': b'\x01' * 32,
        'validator_index': 1,
        'pubkey': 123,
        'flag': 1,
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
def ejection_balance():
    return SERENITY_CONFIG.EJECTION_BALANCE


@pytest.fixture
def max_balance_churn_quotient():
    return SERENITY_CONFIG.MAX_BALANCE_CHURN_QUOTIENT


@pytest.fixture
def beacon_chain_shard_number():
    return SERENITY_CONFIG.BEACON_CHAIN_SHARD_NUMBER


@pytest.fixture
def bls_withdrawal_prefix_byte():
    return SERENITY_CONFIG.BLS_WITHDRAWAL_PREFIX_BYTE


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
def initial_fork_version():
    return SERENITY_CONFIG.INITIAL_FORK_VERSION


@pytest.fixture
def initial_slot_number():
    return SERENITY_CONFIG.INITIAL_SLOT_NUMBER


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
# startup and genesis
#
@pytest.fixture
def startup_state(sample_beacon_state_params,
                  genesis_validators,
                  epoch_length,
                  target_committee_size,
                  initial_slot_number,
                  shard_count,
                  latest_block_roots_length):
    initial_shuffling = get_new_shuffling(
        seed=ZERO_HASH32,
        validators=genesis_validators,
        crosslinking_start_shard=0,
        epoch_length=epoch_length,
        target_committee_size=target_committee_size,
        shard_count=shard_count
    )

    return BeaconState(**sample_beacon_state_params).copy(
        validator_registry=genesis_validators,
        shard_committees_at_slots=initial_shuffling + initial_shuffling,
        latest_block_roots=tuple(ZERO_HASH32 for _ in range(latest_block_roots_length)),
        latest_crosslinks=tuple(
            CrosslinkRecord(
                slot=initial_slot_number,
                shard_block_root=ZERO_HASH32,
            )
            for _ in range(shard_count)
        )
    )


@pytest.fixture
def genesis_validators(init_validator_keys,
                       init_randao,
                       max_deposit):
    return tuple(
        ValidatorRecord(
            pubkey=pub,
            withdrawal_credentials=ZERO_HASH32,
            randao_commitment=init_randao,
            randao_layers=0,
            status=ValidatorStatusCode.ACTIVE,
            latest_status_change_slot=0,
            exit_count=0,
        ) for pub in init_validator_keys
    )


@pytest.fixture
def genesis_block(startup_state, initial_slot_number):
    return BeaconBlock(
        slot=initial_slot_number,
        parent_root=ZERO_HASH32,
        state_root=startup_state.root,
        randao_reveal=ZERO_HASH32,
        candidate_pow_receipt_root=ZERO_HASH32,
        signature=EMPTY_SIGNATURE,
        body=BeaconBlockBody(
            proposer_slashings=(),
            casper_slashings=(),
            attestations=(),
            deposits=(),
            exits=(),
        ),
    )


#
# StateMachine
#
@pytest.fixture
def config(
        shard_count,
        target_committee_size,
        ejection_balance,
        max_balance_churn_quotient,
        beacon_chain_shard_number,
        bls_withdrawal_prefix_byte,
        max_casper_votes,
        latest_block_roots_length,
        latest_randao_mixes_length,
        deposit_contract_address,
        deposit_contract_tree_depth,
        min_deposit,
        max_deposit,
        initial_fork_version,
        initial_slot_number,
        slot_duration,
        min_attestation_inclusion_delay,
        epoch_length,
        pow_receipt_root_voting_period,
        shard_persistent_committee_change_period,
        collective_penalty_calculation_period,
        zero_balance_validator_ttl,
        base_reward_quotient,
        whistleblower_reward_quotient,
        includer_reward_quotient,
        inactivity_penalty_quotient,
        max_proposer_slashings,
        max_casper_slashings,
        max_attestations,
        max_deposits,
        max_exits
):
    return BeaconConfig(
        SHARD_COUNT=shard_count,
        TARGET_COMMITTEE_SIZE=target_committee_size,
        EJECTION_BALANCE=ejection_balance,
        MAX_BALANCE_CHURN_QUOTIENT=max_balance_churn_quotient,
        BEACON_CHAIN_SHARD_NUMBER=beacon_chain_shard_number,
        BLS_WITHDRAWAL_PREFIX_BYTE=bls_withdrawal_prefix_byte,
        MAX_CASPER_VOTES=max_casper_votes,
        LATEST_BLOCK_ROOTS_LENGTH=latest_block_roots_length,
        LATEST_RANDAO_MIXES_LENGTH=latest_randao_mixes_length,
        DEPOSIT_CONTRACT_ADDRESS=deposit_contract_address,
        DEPOSIT_CONTRACT_TREE_DEPTH=deposit_contract_tree_depth,
        MIN_DEPOSIT=min_deposit,
        MAX_DEPOSIT=max_deposit,
        INITIAL_FORK_VERSION=initial_fork_version,
        INITIAL_SLOT_NUMBER=initial_slot_number,
        SLOT_DURATION=slot_duration,
        MIN_ATTESTATION_INCLUSION_DELAY=min_attestation_inclusion_delay,
        EPOCH_LENGTH=epoch_length,
        POW_RECEIPT_ROOT_VOTING_PERIOD=pow_receipt_root_voting_period,
        SHARD_PERSISTENT_COMMITTEE_CHANGE_PERIOD=shard_persistent_committee_change_period,
        COLLECTIVE_PENALTY_CALCULATION_PERIOD=collective_penalty_calculation_period,
        ZERO_BALANCE_VALIDATOR_TTL=zero_balance_validator_ttl,
        BASE_REWARD_QUOTIENT=base_reward_quotient,
        WHISTLEBLOWER_REWARD_QUOTIENT=whistleblower_reward_quotient,
        INCLUDER_REWARD_QUOTIENT=includer_reward_quotient,
        INACTIVITY_PENALTY_QUOTIENT=inactivity_penalty_quotient,
        MAX_PROPOSER_SLASHINGS=max_proposer_slashings,
        MAX_CASPER_SLASHINGS=max_casper_slashings,
        MAX_ATTESTATIONS=max_attestations,
        MAX_DEPOSITS=max_deposits,
        MAX_EXITS=max_exits,
    )


#
# State machine
#
@pytest.fixture
def fixture_sm_class(config):
    return SerenityStateMachine.configure(
        __name__='SerenityStateMachineForTesting',
        config=config,
    )


#
# Create mock consensus objects
#
@pytest.fixture
def create_mock_signed_attestation(privkeys):
    def create_mock_signed_attestation(state,
                                       shard_committee,
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
                privkeys[shard_committee.committee[committee_index]],
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
            bitfield=get_empty_bitfield(len(shard_committee.committee)),
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
