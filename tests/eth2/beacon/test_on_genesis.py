import pytest

from eth.constants import (
    ZERO_HASH32,
)

from eth2.beacon.constants import (
    EMPTY_SIGNATURE,
)
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.types.crosslink_records import CrosslinkRecord
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.deposit_data import DepositData
from eth2.beacon.types.deposit_input import DepositInput
from eth2.beacon.types.eth1_data import Eth1Data
from eth2.beacon.types.forks import Fork

from eth2.beacon.on_genesis import (
    get_genesis_block,
    get_genesis_beacon_state,
)
from eth2.beacon.tools.builder.validator import (
    sign_proof_of_possession,
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
        privkeys,
        pubkeys,
        num_validators,
        genesis_epoch,
        genesis_slot,
        genesis_fork_version,
        genesis_start_shard,
        shard_count,
        min_seed_lookahead,
        latest_block_roots_length,
        latest_active_index_roots_length,
        slots_per_epoch,
        max_deposit_amount,
        latest_slashed_exit_length,
        latest_randao_mixes_length,
        activation_exit_delay,
        sample_eth1_data_params):
    withdrawal_credentials = b'\x22' * 32
    fork = Fork(
        previous_version=genesis_fork_version.to_bytes(4, 'little'),
        current_version=genesis_fork_version.to_bytes(4, 'little'),
        epoch=genesis_epoch,
    )

    validator_count = 5

    genesis_validator_deposits = tuple(
        Deposit(
            branch=(
                b'\x11' * 32
                for j in range(10)
            ),
            index=i,
            deposit_data=DepositData(
                deposit_input=DepositInput(
                    pubkey=pubkeys[i],
                    withdrawal_credentials=withdrawal_credentials,
                    proof_of_possession=sign_proof_of_possession(
                        deposit_input=DepositInput(
                            pubkey=pubkeys[i],
                            withdrawal_credentials=withdrawal_credentials,
                        ),
                        privkey=privkeys[i],
                        fork=fork,
                        slot=genesis_slot,
                        slots_per_epoch=slots_per_epoch,
                    ),
                ),
                amount=max_deposit_amount,
                timestamp=0,
            ),
        )
        for i in range(validator_count)
    )
    genesis_time = 10
    latest_eth1_data = Eth1Data(**sample_eth1_data_params)

    state = get_genesis_beacon_state(
        genesis_validator_deposits=genesis_validator_deposits,
        genesis_time=genesis_time,
        latest_eth1_data=latest_eth1_data,
        genesis_epoch=genesis_epoch,
        genesis_slot=genesis_slot,
        genesis_fork_version=genesis_fork_version,
        genesis_start_shard=genesis_start_shard,
        shard_count=shard_count,
        min_seed_lookahead=min_seed_lookahead,
        latest_block_roots_length=latest_block_roots_length,
        latest_active_index_roots_length=latest_active_index_roots_length,
        slots_per_epoch=slots_per_epoch,
        max_deposit_amount=max_deposit_amount,
        latest_slashed_exit_length=latest_slashed_exit_length,
        latest_randao_mixes_length=latest_randao_mixes_length,
        activation_exit_delay=activation_exit_delay,
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
    assert len(state.latest_block_roots) == latest_block_roots_length
    assert state.latest_block_roots[0] == ZERO_HASH32
    assert len(state.latest_slashed_balances) == latest_slashed_exit_length
    assert state.latest_slashed_balances[0] == Gwei(0)

    assert len(state.latest_attestations) == 0
    assert len(state.batched_block_roots) == 0

    # Ethereum 1.0 chain data
    assert state.latest_eth1_data == latest_eth1_data
    assert len(state.eth1_data_votes) == 0
    assert state.deposit_index == len(genesis_validator_deposits)

    assert state.validator_registry[0].is_active(genesis_epoch)
