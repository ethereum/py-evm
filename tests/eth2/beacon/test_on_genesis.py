import pytest

from eth.constants import (
    ZERO_HASH32,
)

from eth2.beacon.constants import (
    EMPTY_SIGNATURE,
)
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.types.crosslink_records import CrosslinkRecord
from eth2.beacon.types.eth1_data import Eth1Data

from eth2.beacon.on_genesis import (
    get_genesis_block,
    get_genesis_beacon_state,
)
from eth2.beacon.tools.builder.initializer import (
    create_mock_genesis_validator_deposits_and_root,
)
from eth2.beacon.typing import (
    Gwei,
)


def test_get_genesis_block():
    genesis_state_root = b'\x10' * 32
    genesis_slot = 10
    genesis_block = get_genesis_block(genesis_state_root, genesis_slot, BeaconBlock)
    assert genesis_block.slot == genesis_slot
    assert genesis_block.parent_root == ZERO_HASH32
    assert genesis_block.state_root == genesis_state_root
    assert genesis_block.randao_reveal == EMPTY_SIGNATURE
    assert genesis_block.eth1_data == Eth1Data.create_empty_data()
    assert genesis_block.signature == EMPTY_SIGNATURE
    assert genesis_block.body.is_empty


@pytest.mark.parametrize(
    (
        'num_validators,'
    ),
    [
        (10)
    ]
)
def test_get_genesis_beacon_state(
        num_validators,
        pubkeys,
        genesis_epoch,
        genesis_slot,
        genesis_fork_version,
        genesis_start_shard,
        shard_count,
        min_seed_lookahead,
        slots_per_historical_root,
        latest_active_index_roots_length,
        slots_per_epoch,
        max_deposit_amount,
        latest_slashed_exit_length,
        latest_randao_mixes_length,
        activation_exit_delay,
        config,
        keymap,
        deposit_contract_tree_depth):
    validator_count = 5

    genesis_validator_deposits, deposit_root = create_mock_genesis_validator_deposits_and_root(
        num_validators=validator_count,
        config=config,
        pubkeys=pubkeys,
        keymap=keymap,
    )

    genesis_eth1_data = Eth1Data(
        deposit_root=deposit_root,
        block_hash=ZERO_HASH32,
    )
    genesis_time = 10

    state = get_genesis_beacon_state(
        genesis_validator_deposits=genesis_validator_deposits,
        genesis_time=genesis_time,
        genesis_eth1_data=genesis_eth1_data,
        genesis_epoch=genesis_epoch,
        genesis_slot=genesis_slot,
        genesis_fork_version=genesis_fork_version,
        genesis_start_shard=genesis_start_shard,
        shard_count=shard_count,
        min_seed_lookahead=min_seed_lookahead,
        slots_per_historical_root=slots_per_historical_root,
        latest_active_index_roots_length=latest_active_index_roots_length,
        slots_per_epoch=slots_per_epoch,
        max_deposit_amount=max_deposit_amount,
        latest_slashed_exit_length=latest_slashed_exit_length,
        latest_randao_mixes_length=latest_randao_mixes_length,
        activation_exit_delay=activation_exit_delay,
        deposit_contract_tree_depth=deposit_contract_tree_depth,
    )

    # Misc
    assert state.slot == genesis_slot
    assert state.genesis_time == genesis_time
    assert state.fork.previous_version == genesis_fork_version.to_bytes(4, 'little')
    assert state.fork.current_version == genesis_fork_version.to_bytes(4, 'little')
    assert state.fork.epoch == genesis_epoch

    # Validator registry
    assert len(state.validator_registry) == validator_count
    assert len(state.validator_balances) == validator_count
    assert state.validator_registry_update_epoch == genesis_epoch

    # Randomness and committees
    assert len(state.latest_randao_mixes) == latest_randao_mixes_length
    assert state.previous_shuffling_start_shard == genesis_start_shard
    assert state.current_shuffling_start_shard == genesis_start_shard
    assert state.previous_shuffling_epoch == genesis_epoch
    assert state.current_shuffling_epoch == genesis_epoch
    assert state.previous_shuffling_seed == ZERO_HASH32

    # Finality
    assert len(state.previous_epoch_attestations) == 0
    assert len(state.current_epoch_attestations) == 0
    assert state.previous_justified_epoch == genesis_epoch
    assert state.justified_epoch == genesis_epoch
    assert state.justification_bitfield == 0
    assert state.finalized_epoch == genesis_epoch

    # Recent state
    assert len(state.latest_crosslinks) == shard_count
    assert state.latest_crosslinks[0] == CrosslinkRecord(
        epoch=genesis_epoch,
        crosslink_data_root=ZERO_HASH32,
    )
    assert len(state.latest_block_roots) == slots_per_historical_root
    assert state.latest_block_roots[0] == ZERO_HASH32
    assert len(state.latest_slashed_balances) == latest_slashed_exit_length
    assert state.latest_slashed_balances[0] == Gwei(0)

    assert len(state.historical_roots) == 0

    # Ethereum 1.0 chain data
    assert state.latest_eth1_data == genesis_eth1_data
    assert len(state.eth1_data_votes) == 0
    assert state.deposit_index == len(genesis_validator_deposits)

    assert state.validator_registry[0].is_active(genesis_epoch)
