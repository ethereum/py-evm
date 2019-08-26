from eth.constants import ZERO_HASH32
from eth_typing import BLSPubkey
import pytest

from eth2.beacon.constants import (
    DEPOSIT_CONTRACT_TREE_DEPTH,
    FAR_FUTURE_EPOCH,
    GWEI_PER_ETH,
    JUSTIFICATION_BITS_LENGTH,
)
from eth2.beacon.db.chain import BeaconChainDB
from eth2.beacon.fork_choice.higher_slot import higher_slot_scoring
from eth2.beacon.genesis import get_genesis_block
from eth2.beacon.operations.attestation_pool import AttestationPool
from eth2.beacon.state_machines.forks.serenity import SerenityStateMachine
from eth2.beacon.state_machines.forks.serenity.blocks import SerenityBeaconBlock
from eth2.beacon.state_machines.forks.serenity.configs import SERENITY_CONFIG
from eth2.beacon.tools.builder.initializer import create_mock_validator
from eth2.beacon.tools.builder.state import create_mock_genesis_state_from_validators
from eth2.beacon.tools.misc.ssz_vector import override_lengths
from eth2.beacon.types.attestation_data import AttestationData
from eth2.beacon.types.attestations import IndexedAttestation
from eth2.beacon.types.blocks import BeaconBlock, BeaconBlockBody, BeaconBlockHeader
from eth2.beacon.types.checkpoints import Checkpoint
from eth2.beacon.types.crosslinks import Crosslink
from eth2.beacon.types.deposit_data import DepositData
from eth2.beacon.types.eth1_data import Eth1Data
from eth2.beacon.types.forks import Fork
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import Gwei, Timestamp, ValidatorIndex, Version
from eth2.configs import CommitteeConfig, Eth2Config, Eth2GenesisConfig


# SSZ
@pytest.fixture(scope="function", autouse=True)
def override_ssz_lengths(config):
    override_lengths(config)


#
# Config
#
@pytest.fixture
def shard_count():
    return SERENITY_CONFIG.SHARD_COUNT


@pytest.fixture
def target_committee_size():
    return SERENITY_CONFIG.TARGET_COMMITTEE_SIZE


@pytest.fixture
def max_validators_per_committee():
    return SERENITY_CONFIG.MAX_VALIDATORS_PER_COMMITTEE


@pytest.fixture
def min_per_epoch_churn_limit():
    return SERENITY_CONFIG.MIN_PER_EPOCH_CHURN_LIMIT


@pytest.fixture
def churn_limit_quotient():
    return SERENITY_CONFIG.CHURN_LIMIT_QUOTIENT


@pytest.fixture
def shuffle_round_count():
    return SERENITY_CONFIG.SHUFFLE_ROUND_COUNT


@pytest.fixture
def min_genesis_active_validator_count():
    return SERENITY_CONFIG.MIN_GENESIS_ACTIVE_VALIDATOR_COUNT


@pytest.fixture
def min_genesis_time():
    return SERENITY_CONFIG.MIN_GENESIS_TIME


@pytest.fixture
def min_deposit_amount():
    return SERENITY_CONFIG.MIN_DEPOSIT_AMOUNT


@pytest.fixture
def max_effective_balance():
    return SERENITY_CONFIG.MAX_EFFECTIVE_BALANCE


@pytest.fixture
def ejection_balance():
    return SERENITY_CONFIG.EJECTION_BALANCE


@pytest.fixture
def effective_balance_increment():
    return SERENITY_CONFIG.EFFECTIVE_BALANCE_INCREMENT


@pytest.fixture
def genesis_slot():
    return SERENITY_CONFIG.GENESIS_SLOT


@pytest.fixture
def genesis_epoch():
    return SERENITY_CONFIG.GENESIS_EPOCH


@pytest.fixture
def bls_withdrawal_prefix():
    return SERENITY_CONFIG.BLS_WITHDRAWAL_PREFIX


@pytest.fixture
def seconds_per_slot():
    return SERENITY_CONFIG.SECONDS_PER_SLOT


@pytest.fixture
def min_attestation_inclusion_delay():
    return SERENITY_CONFIG.MIN_ATTESTATION_INCLUSION_DELAY


@pytest.fixture
def slots_per_epoch():
    return SERENITY_CONFIG.SLOTS_PER_EPOCH


@pytest.fixture
def min_seed_lookahead():
    return SERENITY_CONFIG.MIN_SEED_LOOKAHEAD


@pytest.fixture
def activation_exit_delay():
    return SERENITY_CONFIG.ACTIVATION_EXIT_DELAY


@pytest.fixture
def slots_per_eth1_voting_period():
    return SERENITY_CONFIG.SLOTS_PER_ETH1_VOTING_PERIOD


@pytest.fixture
def slots_per_historical_root():
    return SERENITY_CONFIG.SLOTS_PER_HISTORICAL_ROOT


@pytest.fixture
def min_validator_withdrawability_delay():
    return SERENITY_CONFIG.MIN_VALIDATOR_WITHDRAWABILITY_DELAY


@pytest.fixture
def persistent_committee_period():
    return SERENITY_CONFIG.PERSISTENT_COMMITTEE_PERIOD


@pytest.fixture
def max_epochs_per_crosslink():
    return SERENITY_CONFIG.MAX_EPOCHS_PER_CROSSLINK


@pytest.fixture
def min_epochs_to_inactivity_penalty():
    return SERENITY_CONFIG.MIN_EPOCHS_TO_INACTIVITY_PENALTY


@pytest.fixture
def epochs_per_historical_vector():
    return SERENITY_CONFIG.EPOCHS_PER_HISTORICAL_VECTOR


@pytest.fixture
def epochs_per_slashings_vector():
    return SERENITY_CONFIG.EPOCHS_PER_SLASHINGS_VECTOR


@pytest.fixture
def historical_roots_limit():
    return SERENITY_CONFIG.HISTORICAL_ROOTS_LIMIT


@pytest.fixture
def validator_registry_limit():
    return SERENITY_CONFIG.VALIDATOR_REGISTRY_LIMIT


@pytest.fixture
def base_reward_factor():
    return SERENITY_CONFIG.BASE_REWARD_FACTOR


@pytest.fixture
def whistleblower_reward_quotient():
    return SERENITY_CONFIG.WHISTLEBLOWER_REWARD_QUOTIENT


@pytest.fixture
def proposer_reward_quotient():
    return SERENITY_CONFIG.PROPOSER_REWARD_QUOTIENT


@pytest.fixture
def inactivity_penalty_quotient():
    return SERENITY_CONFIG.INACTIVITY_PENALTY_QUOTIENT


@pytest.fixture
def min_slashing_penalty_quotient():
    return SERENITY_CONFIG.MIN_SLASHING_PENALTY_QUOTIENT


@pytest.fixture
def max_proposer_slashings():
    return SERENITY_CONFIG.MAX_PROPOSER_SLASHINGS


@pytest.fixture
def max_attester_slashings():
    return SERENITY_CONFIG.MAX_ATTESTER_SLASHINGS


@pytest.fixture
def max_attestations():
    return SERENITY_CONFIG.MAX_ATTESTATIONS


@pytest.fixture
def max_deposits():
    return SERENITY_CONFIG.MAX_DEPOSITS


@pytest.fixture
def max_voluntary_exits():
    return SERENITY_CONFIG.MAX_VOLUNTARY_EXITS


@pytest.fixture
def max_transfers():
    return SERENITY_CONFIG.MAX_TRANSFERS


@pytest.fixture
def deposit_contract_tree_depth():
    return DEPOSIT_CONTRACT_TREE_DEPTH


@pytest.fixture
def deposit_contract_address():
    return SERENITY_CONFIG.DEPOSIT_CONTRACT_ADDRESS


@pytest.fixture
def config(
    shard_count,
    target_committee_size,
    max_validators_per_committee,
    min_per_epoch_churn_limit,
    churn_limit_quotient,
    shuffle_round_count,
    min_genesis_active_validator_count,
    min_genesis_time,
    min_deposit_amount,
    max_effective_balance,
    ejection_balance,
    effective_balance_increment,
    genesis_slot,
    genesis_epoch,
    bls_withdrawal_prefix,
    seconds_per_slot,
    min_attestation_inclusion_delay,
    slots_per_epoch,
    min_seed_lookahead,
    activation_exit_delay,
    slots_per_eth1_voting_period,
    slots_per_historical_root,
    min_validator_withdrawability_delay,
    persistent_committee_period,
    max_epochs_per_crosslink,
    min_epochs_to_inactivity_penalty,
    epochs_per_historical_vector,
    epochs_per_slashings_vector,
    historical_roots_limit,
    validator_registry_limit,
    base_reward_factor,
    whistleblower_reward_quotient,
    proposer_reward_quotient,
    inactivity_penalty_quotient,
    min_slashing_penalty_quotient,
    max_proposer_slashings,
    max_attester_slashings,
    max_attestations,
    max_deposits,
    max_voluntary_exits,
    max_transfers,
    deposit_contract_address,
):
    # adding some config validity conditions here
    # abstract out into the config object?
    assert shard_count >= slots_per_epoch

    return Eth2Config(
        SHARD_COUNT=shard_count,
        TARGET_COMMITTEE_SIZE=target_committee_size,
        MAX_VALIDATORS_PER_COMMITTEE=max_validators_per_committee,
        MIN_PER_EPOCH_CHURN_LIMIT=min_per_epoch_churn_limit,
        CHURN_LIMIT_QUOTIENT=churn_limit_quotient,
        SHUFFLE_ROUND_COUNT=shuffle_round_count,
        MIN_GENESIS_ACTIVE_VALIDATOR_COUNT=min_genesis_active_validator_count,
        MIN_GENESIS_TIME=min_genesis_time,
        MIN_DEPOSIT_AMOUNT=min_deposit_amount,
        MAX_EFFECTIVE_BALANCE=max_effective_balance,
        EJECTION_BALANCE=ejection_balance,
        EFFECTIVE_BALANCE_INCREMENT=effective_balance_increment,
        GENESIS_SLOT=genesis_slot,
        GENESIS_EPOCH=genesis_epoch,
        BLS_WITHDRAWAL_PREFIX=bls_withdrawal_prefix,
        SECONDS_PER_SLOT=seconds_per_slot,
        MIN_ATTESTATION_INCLUSION_DELAY=min_attestation_inclusion_delay,
        SLOTS_PER_EPOCH=slots_per_epoch,
        MIN_SEED_LOOKAHEAD=min_seed_lookahead,
        ACTIVATION_EXIT_DELAY=activation_exit_delay,
        SLOTS_PER_ETH1_VOTING_PERIOD=slots_per_eth1_voting_period,
        SLOTS_PER_HISTORICAL_ROOT=slots_per_historical_root,
        MIN_VALIDATOR_WITHDRAWABILITY_DELAY=min_validator_withdrawability_delay,
        PERSISTENT_COMMITTEE_PERIOD=persistent_committee_period,
        MAX_EPOCHS_PER_CROSSLINK=max_epochs_per_crosslink,
        MIN_EPOCHS_TO_INACTIVITY_PENALTY=min_epochs_to_inactivity_penalty,
        EPOCHS_PER_HISTORICAL_VECTOR=epochs_per_historical_vector,
        EPOCHS_PER_SLASHINGS_VECTOR=epochs_per_slashings_vector,
        HISTORICAL_ROOTS_LIMIT=historical_roots_limit,
        VALIDATOR_REGISTRY_LIMIT=validator_registry_limit,
        BASE_REWARD_FACTOR=base_reward_factor,
        WHISTLEBLOWER_REWARD_QUOTIENT=whistleblower_reward_quotient,
        PROPOSER_REWARD_QUOTIENT=proposer_reward_quotient,
        INACTIVITY_PENALTY_QUOTIENT=inactivity_penalty_quotient,
        MIN_SLASHING_PENALTY_QUOTIENT=min_slashing_penalty_quotient,
        MAX_PROPOSER_SLASHINGS=max_proposer_slashings,
        MAX_ATTESTER_SLASHINGS=max_attester_slashings,
        MAX_ATTESTATIONS=max_attestations,
        MAX_DEPOSITS=max_deposits,
        MAX_VOLUNTARY_EXITS=max_voluntary_exits,
        MAX_TRANSFERS=max_transfers,
        DEPOSIT_CONTRACT_ADDRESS=deposit_contract_address,
    )


@pytest.fixture
def committee_config(config):
    return CommitteeConfig(config)


@pytest.fixture
def genesis_config(config):
    return Eth2GenesisConfig(config)


#
# Sample data params
#
@pytest.fixture
def sample_signature():
    return b"\56" * 96


@pytest.fixture
def sample_fork_params():
    return {
        "previous_version": Version((0).to_bytes(4, "little")),
        "current_version": Version((0).to_bytes(4, "little")),
        "epoch": 2 ** 32,
    }


@pytest.fixture
def sample_validator_record_params():
    return {
        "pubkey": b"\x67" * 48,
        "withdrawal_credentials": b"\x01" * 32,
        "effective_balance": Gwei(32 * GWEI_PER_ETH),
        "slashed": False,
        "activation_eligibility_epoch": FAR_FUTURE_EPOCH,
        "activation_epoch": FAR_FUTURE_EPOCH,
        "exit_epoch": FAR_FUTURE_EPOCH,
        "withdrawable_epoch": FAR_FUTURE_EPOCH,
    }


@pytest.fixture
def sample_crosslink_record_params():
    return {
        "shard": 0,
        "parent_root": b"\x34" * 32,
        "start_epoch": 0,
        "end_epoch": 1,
        "data_root": b"\x43" * 32,
    }


@pytest.fixture
def sample_attestation_data_params(sample_crosslink_record_params):
    return {
        "beacon_block_root": b"\x11" * 32,
        "source": Checkpoint(epoch=11, root=b"\x22" * 32),
        "target": Checkpoint(epoch=12, root=b"\x33" * 32),
        "crosslink": Crosslink(**sample_crosslink_record_params),
    }


@pytest.fixture
def sample_attestation_data_and_custody_bit_params(sample_attestation_data_params):
    return {
        "data": AttestationData(**sample_attestation_data_params),
        "custody_bit": False,
    }


@pytest.fixture
def sample_indexed_attestation_params(sample_signature, sample_attestation_data_params):
    return {
        "custody_bit_0_indices": (10, 11, 12, 15, 28),
        "custody_bit_1_indices": tuple(),
        "data": AttestationData(**sample_attestation_data_params),
        "signature": sample_signature,
    }


@pytest.fixture
def sample_pending_attestation_record_params(sample_attestation_data_params):
    return {
        "aggregation_bits": (True, False) * 4 * 16,
        "data": AttestationData(**sample_attestation_data_params),
        "inclusion_delay": 1,
        "proposer_index": ValidatorIndex(12),
    }


@pytest.fixture
def sample_eth1_data_params():
    return {
        "deposit_root": b"\x43" * 32,
        "deposit_count": 22,
        "block_hash": b"\x46" * 32,
    }


@pytest.fixture
def sample_historical_batch_params(config):
    return {
        "block_roots": tuple(
            (bytes([i] * 32) for i in range(config.SLOTS_PER_HISTORICAL_ROOT))
        ),
        "state_roots": tuple(
            (bytes([i] * 32) for i in range(config.SLOTS_PER_HISTORICAL_ROOT))
        ),
    }


@pytest.fixture
def sample_deposit_data_params(sample_signature):
    return {
        "pubkey": BLSPubkey(b"\x67" * 48),
        "withdrawal_credentials": b"\11" * 32,
        "amount": Gwei(56),
        "signature": sample_signature,
    }


@pytest.fixture
def sample_block_header_params():
    return {
        "slot": 10,
        "parent_root": b"\x22" * 32,
        "state_root": b"\x33" * 32,
        "body_root": b"\x43" * 32,
        "signature": b"\x56" * 96,
    }


@pytest.fixture
def sample_proposer_slashing_params(sample_block_header_params):
    block_header_data = BeaconBlockHeader(**sample_block_header_params)
    return {
        "proposer_index": 1,
        "header_1": block_header_data,
        "header_2": block_header_data,
    }


@pytest.fixture
def sample_attester_slashing_params(sample_indexed_attestation_params):
    indexed_attestation = IndexedAttestation(**sample_indexed_attestation_params)
    return {"attestation_1": indexed_attestation, "attestation_2": indexed_attestation}


@pytest.fixture
def sample_attestation_params(sample_signature, sample_attestation_data_params):
    return {
        "aggregation_bits": (True,) * 16,
        "data": AttestationData(**sample_attestation_data_params),
        "custody_bits": (False,) * 16,
        "signature": sample_signature,
    }


@pytest.fixture
def sample_deposit_params(sample_deposit_data_params, deposit_contract_tree_depth):
    return {
        "proof": (b"\x22" * 32,) * (deposit_contract_tree_depth + 1),
        "data": DepositData(**sample_deposit_data_params),
    }


@pytest.fixture
def sample_voluntary_exit_params(sample_signature):
    return {"epoch": 123, "validator_index": 15, "signature": sample_signature}


@pytest.fixture
def sample_transfer_params():
    return {
        "sender": 10,
        "recipient": 12,
        "amount": 10 * 10 ** 9,
        "fee": 5 * 10 ** 9,
        "slot": 5,
        "pubkey": b"\x67" * 48,
        "signature": b"\x43" * 96,
    }


@pytest.fixture
def sample_beacon_block_body_params(sample_signature, sample_eth1_data_params):
    return {
        "randao_reveal": sample_signature,
        "eth1_data": Eth1Data(**sample_eth1_data_params),
        "graffiti": ZERO_HASH32,
        "proposer_slashings": (),
        "attester_slashings": (),
        "attestations": (),
        "deposits": (),
        "voluntary_exits": (),
        "transfers": (),
    }


@pytest.fixture
def sample_beacon_block_params(
    sample_signature, sample_beacon_block_body_params, genesis_slot
):
    return {
        "slot": genesis_slot + 10,
        "parent_root": ZERO_HASH32,
        "state_root": b"\x55" * 32,
        "body": BeaconBlockBody(**sample_beacon_block_body_params),
        "signature": sample_signature,
    }


@pytest.fixture
def sample_beacon_state_params(
    config,
    genesis_slot,
    genesis_epoch,
    sample_fork_params,
    sample_eth1_data_params,
    sample_block_header_params,
    sample_crosslink_record_params,
):
    return {
        # Versioning
        "genesis_time": 0,
        "slot": genesis_slot + 100,
        "fork": Fork(**sample_fork_params),
        # History
        "latest_block_header": BeaconBlockHeader(**sample_block_header_params),
        "block_roots": (ZERO_HASH32,) * config.SLOTS_PER_HISTORICAL_ROOT,
        "state_roots": (ZERO_HASH32,) * config.SLOTS_PER_HISTORICAL_ROOT,
        "historical_roots": (),
        # Eth1
        "eth1_data": Eth1Data(**sample_eth1_data_params),
        "eth1_data_votes": (),
        "eth1_deposit_index": 0,
        # Registry
        "validators": (),
        "balances": (),
        # Shuffling
        "start_shard": 1,
        "randao_mixes": (ZERO_HASH32,) * config.EPOCHS_PER_HISTORICAL_VECTOR,
        "active_index_roots": (ZERO_HASH32,) * config.EPOCHS_PER_HISTORICAL_VECTOR,
        "compact_committees_roots": (ZERO_HASH32,)
        * config.EPOCHS_PER_HISTORICAL_VECTOR,
        # Slashings
        "slashings": (0,) * config.EPOCHS_PER_SLASHINGS_VECTOR,
        # Attestations
        "previous_epoch_attestations": (),
        "current_epoch_attestations": (),
        # Crosslinks
        "previous_crosslinks": (
            (Crosslink(**sample_crosslink_record_params),) * config.SHARD_COUNT
        ),
        "current_crosslinks": (
            (Crosslink(**sample_crosslink_record_params),) * config.SHARD_COUNT
        ),
        # Justification
        "justification_bits": (False,) * JUSTIFICATION_BITS_LENGTH,
        "previous_justified_checkpoint": Checkpoint(epoch=0, root=b"\x99" * 32),
        "current_justified_checkpoint": Checkpoint(epoch=0, root=b"\x55" * 32),
        # Finality
        "finalized_checkpoint": Checkpoint(epoch=0, root=b"\x33" * 32),
    }


@pytest.fixture()
def sample_block(sample_beacon_block_params):
    return SerenityBeaconBlock(**sample_beacon_block_params)


@pytest.fixture()
def sample_state(sample_beacon_state_params):
    return BeaconState(**sample_beacon_state_params)


#
# Genesis
#
@pytest.fixture
def genesis_time():
    return Timestamp(1578096000)


@pytest.fixture
def genesis_validators(validator_count, pubkeys, config):
    """
    Returns ``validator_count`` number of activated validators.
    """
    return tuple(
        create_mock_validator(pubkey=pubkey, config=config)
        for pubkey in pubkeys[:validator_count]
    )


@pytest.fixture
def genesis_balances(validator_count, max_effective_balance):
    return (max_effective_balance,) * validator_count


@pytest.fixture
def genesis_state(
    genesis_validators, genesis_balances, genesis_time, sample_eth1_data_params, config
):
    genesis_eth1_data = Eth1Data(**sample_eth1_data_params).copy(
        deposit_count=len(genesis_validators)
    )

    return create_mock_genesis_state_from_validators(
        genesis_time, genesis_eth1_data, genesis_validators, genesis_balances, config
    )


@pytest.fixture
def genesis_block(genesis_state):
    return get_genesis_block(genesis_state.hash_tree_root, SerenityBeaconBlock)


#
# State machine
#
@pytest.fixture
def fixture_sm_class(config, fork_choice_scoring):
    return SerenityStateMachine.configure(
        __name__="SerenityStateMachineForTesting",
        config=config,
        get_fork_choice_scoring=lambda self: fork_choice_scoring,
    )


@pytest.fixture
def fork_choice_scoring():
    return higher_slot_scoring


#
# ChainDB
#
@pytest.fixture
def chaindb(base_db, genesis_config):
    return BeaconChainDB(base_db, genesis_config)


@pytest.fixture
def chaindb_at_genesis(chaindb, genesis_state, genesis_block, fork_choice_scoring):
    chaindb.persist_state(genesis_state)
    chaindb.persist_block(genesis_block, BeaconBlock, fork_choice_scoring)
    return chaindb


#
# Attestation pool
#
@pytest.fixture
def empty_attestation_pool():
    return AttestationPool()


#
# Testing runtime
#
@pytest.fixture()
def validator_count():
    """
    NOTE:
    * By default, a number of BLS public keys equal to this number
      will be created when using the ``genesis_validators`` fixture.
      High validator count can make this expensive quickly!

      Consider persisting keys across runs (cf. ``BLSKeyCache`` class)
    """
    return 10
