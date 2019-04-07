from typing import (
    Sequence,
    Type,
)

from eth_typing import (
    Hash32,
)

from eth.constants import (
    ZERO_HASH32,
)

from eth2.beacon.deposit_helpers import (
    process_deposit,
)
from eth2.beacon.helpers import (
    generate_seed,
    get_active_validator_indices,
    get_effective_balance,
    get_temporary_block_header,
)
from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
    BeaconBlock,
)
from eth2.beacon.types.crosslink_records import CrosslinkRecord
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.eth1_data import Eth1Data
from eth2.beacon.types.forks import Fork
from eth2.beacon.types.states import BeaconState
from eth2.beacon._utils.hash import hash_eth2
from eth2.beacon.typing import (
    Epoch,
    Gwei,
    Shard,
    Slot,
    Timestamp,
    ValidatorIndex,
)
from eth2.beacon.validator_status_helpers import (
    activate_validator,
)


def get_genesis_block(genesis_state_root: Hash32,
                      genesis_slot: Slot,
                      block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
    return block_class.create_empty_block(genesis_slot).copy(
        state_root=genesis_state_root,
    )


def get_genesis_beacon_state(*,
                             genesis_validator_deposits: Sequence[Deposit],
                             genesis_time: Timestamp,
                             genesis_eth1_data: Eth1Data,
                             genesis_slot: Slot,
                             genesis_epoch: Epoch,
                             genesis_fork_version: int,
                             genesis_start_shard: Shard,
                             shard_count: int,
                             min_seed_lookahead: int,
                             slots_per_historical_root: int,
                             latest_active_index_roots_length: int,
                             slots_per_epoch: int,
                             max_deposit_amount: Gwei,
                             latest_slashed_exit_length: int,
                             latest_randao_mixes_length: int,
                             activation_exit_delay: int,
                             deposit_contract_tree_depth: int,
                             block_class: Type[BaseBeaconBlock]) -> BeaconState:
    state = BeaconState(
        # Misc
        slot=genesis_slot,
        genesis_time=genesis_time,
        fork=Fork(
            previous_version=genesis_fork_version.to_bytes(4, 'little'),
            current_version=genesis_fork_version.to_bytes(4, 'little'),
            epoch=genesis_epoch,
        ),

        # Validator registry
        validator_registry=(),
        validator_balances=(),
        validator_registry_update_epoch=genesis_epoch,

        # Randomness and committees
        latest_randao_mixes=(ZERO_HASH32,) * latest_randao_mixes_length,
        previous_shuffling_start_shard=genesis_start_shard,
        current_shuffling_start_shard=genesis_start_shard,
        previous_shuffling_epoch=genesis_epoch,
        current_shuffling_epoch=genesis_epoch,
        previous_shuffling_seed=ZERO_HASH32,
        current_shuffling_seed=ZERO_HASH32,

        # Finality
        previous_epoch_attestations=(),
        current_epoch_attestations=(),
        previous_justified_epoch=genesis_epoch,
        current_justified_epoch=genesis_epoch,
        previous_justified_root=ZERO_HASH32,
        current_justified_root=ZERO_HASH32,
        justification_bitfield=0,
        finalized_epoch=genesis_epoch,
        finalized_root=ZERO_HASH32,

        # Recent state
        latest_crosslinks=(
            (CrosslinkRecord(epoch=genesis_epoch, crosslink_data_root=ZERO_HASH32),) * shard_count
        ),
        latest_block_roots=(ZERO_HASH32,) * slots_per_historical_root,
        latest_state_roots=(ZERO_HASH32,) * slots_per_historical_root,
        latest_active_index_roots=(ZERO_HASH32,) * latest_active_index_roots_length,
        latest_slashed_balances=(Gwei(0),) * latest_slashed_exit_length,
        latest_block_header=get_temporary_block_header(
            BeaconBlock.create_empty_block(genesis_slot),
        ),
        historical_roots=(),

        # Ethereum 1.0 chain data
        latest_eth1_data=genesis_eth1_data,
        eth1_data_votes=(),
        deposit_index=0,
    )

    # Process genesis deposits
    for deposit in genesis_validator_deposits:
        state = process_deposit(
            state=state,
            deposit=deposit,
            slots_per_epoch=slots_per_epoch,
            deposit_contract_tree_depth=deposit_contract_tree_depth,
        )

    # Process genesis activations
    for validator_index, _ in enumerate(state.validator_registry):
        validator_index = ValidatorIndex(validator_index)
        is_enough_effective_balance = get_effective_balance(
            state.validator_balances,
            validator_index,
            max_deposit_amount,
        ) >= max_deposit_amount
        if is_enough_effective_balance:
            state = activate_validator(
                state=state,
                index=validator_index,
                is_genesis=True,
                genesis_epoch=genesis_epoch,
                slots_per_epoch=slots_per_epoch,
                activation_exit_delay=activation_exit_delay,
            )

    # TODO: chanege to hash_tree_root
    active_validator_indices = get_active_validator_indices(
        state.validator_registry,
        genesis_epoch,
    )
    genesis_active_index_root = hash_eth2(
        b''.join(
            [
                index.to_bytes(32, 'little')
                for index in active_validator_indices
            ]
        )
    )
    latest_active_index_roots = (genesis_active_index_root,) * latest_active_index_roots_length
    state = state.copy(
        latest_active_index_roots=latest_active_index_roots,
    )

    current_shuffling_seed = generate_seed(
        state=state,
        epoch=genesis_epoch,
        slots_per_epoch=slots_per_epoch,
        min_seed_lookahead=min_seed_lookahead,
        activation_exit_delay=activation_exit_delay,
        latest_active_index_roots_length=latest_active_index_roots_length,
        latest_randao_mixes_length=latest_randao_mixes_length,
    )
    state = state.copy(
        current_shuffling_seed=current_shuffling_seed,
    )

    return state
