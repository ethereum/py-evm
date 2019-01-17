import pytest

from eth2.beacon.state_machines.configs import BeaconConfig
from eth2.beacon.state_machines.forks.serenity import (
    SerenityStateMachine,
)


@pytest.fixture
def config(
        shard_count,
        target_committee_size,
        ejection_balance,
        max_balance_churn_quotient,
        beacon_chain_shard_number,
        max_casper_votes,
        latest_block_roots_length,
        latest_randao_mixes_length,
        latest_penalized_exit_length,
        deposit_contract_address,
        deposit_contract_tree_depth,
        min_deposit,
        max_deposit,
        genesis_fork_version,
        genesis_slot,
        bls_withdrawal_prefix_byte,
        slot_duration,
        min_attestation_inclusion_delay,
        epoch_length,
        seed_lookahead,
        entry_exit_delay,
        eth1_data_voting_period,
        min_validator_withdrawal_time,
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
        MAX_CASPER_VOTES=max_casper_votes,
        LATEST_BLOCK_ROOTS_LENGTH=latest_block_roots_length,
        LATEST_RANDAO_MIXES_LENGTH=latest_randao_mixes_length,
        LATEST_PENALIZED_EXIT_LENGTH=latest_penalized_exit_length,
        DEPOSIT_CONTRACT_ADDRESS=deposit_contract_address,
        DEPOSIT_CONTRACT_TREE_DEPTH=deposit_contract_tree_depth,
        MIN_DEPOSIT=min_deposit,
        MAX_DEPOSIT=max_deposit,
        GENESIS_FORK_VERSION=genesis_fork_version,
        GENESIS_SLOT=genesis_slot,
        BLS_WITHDRAWAL_PREFIX_BYTE=bls_withdrawal_prefix_byte,
        SLOT_DURATION=slot_duration,
        MIN_ATTESTATION_INCLUSION_DELAY=min_attestation_inclusion_delay,
        EPOCH_LENGTH=epoch_length,
        SEED_LOOKAHEAD=seed_lookahead,
        ENTRY_EXIT_DELAY=entry_exit_delay,
        ETH1_DATA_VOTING_PERIOD=eth1_data_voting_period,
        MIN_VALIDATOR_WITHDRAWAL_TIME=min_validator_withdrawal_time,
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
