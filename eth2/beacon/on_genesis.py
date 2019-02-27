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

from eth2.beacon.constants import (
    EMPTY_SIGNATURE,
)
from eth2.beacon.deposit_helpers import (
    process_deposit,
)
from eth2.beacon.helpers import (
    generate_seed,
    get_active_validator_indices,
    get_effective_balance,
)
from eth2.beacon.types.blocks import (
    BaseBeaconBlock,
    BeaconBlockBody,
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
    return block_class(
        slot=genesis_slot,
        parent_root=ZERO_HASH32,
        state_root=genesis_state_root,
        randao_reveal=EMPTY_SIGNATURE,
        eth1_data=Eth1Data.create_empty_data(),
        signature=EMPTY_SIGNATURE,
        body=BeaconBlockBody.create_empty_body(),
    )


def get_genesis_beacon_state(*,
                             genesis_validator_deposits: Sequence[Deposit],
                             genesis_time: Timestamp,
                             latest_eth1_data: Eth1Data,
                             genesis_slot: Slot,
                             genesis_epoch: Epoch,
                             genesis_fork_version: int,
                             genesis_start_shard: Shard,
                             shard_count: int,
                             min_seed_lookahead: int,
                             latest_block_roots_length: int,
                             latest_active_index_roots_length: int,
                             slots_per_epoch: int,
                             max_deposit_amount: Gwei,
                             latest_slashed_exit_length: int,
                             latest_randao_mixes_length: int,
                             activation_exit_delay: int) -> BeaconState:
    state = BeaconState(
        # Misc
        slot=genesis_slot,
        genesis_time=genesis_time,
        fork=Fork(
            previous_version=genesis_fork_version,
            current_version=genesis_fork_version,
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
        previous_justified_epoch=genesis_epoch,
        justified_epoch=genesis_epoch,
        justification_bitfield=0,
        finalized_epoch=genesis_epoch,

        # Recent state
        latest_crosslinks=(
            (CrosslinkRecord(epoch=genesis_epoch, crosslink_data_root=ZERO_HASH32),) * shard_count
        ),
        latest_block_roots=(ZERO_HASH32,) * latest_block_roots_length,
        latest_active_index_roots=(ZERO_HASH32,) * latest_active_index_roots_length,
        latest_slashed_balances=(Gwei(0),) * latest_slashed_exit_length,
        latest_attestations=(),
        batched_block_roots=(),

        # Ethereum 1.0 chain data
        latest_eth1_data=latest_eth1_data,
        eth1_data_votes=(),
        deposit_index=len(genesis_validator_deposits),
    )

    # Process genesis deposits
    for deposit in genesis_validator_deposits:
        state = process_deposit(
            state=state,
            pubkey=deposit.deposit_data.deposit_input.pubkey,
            amount=deposit.deposit_data.amount,
            proof_of_possession=deposit.deposit_data.deposit_input.proof_of_possession,
            withdrawal_credentials=deposit.deposit_data.deposit_input.withdrawal_credentials,
            slots_per_epoch=slots_per_epoch,
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
                index.to_bytes(32, 'big')
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
