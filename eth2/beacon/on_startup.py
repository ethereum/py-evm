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

from eth2._utils.tuple import update_tuple_item
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
    EpochNumber,
    Gwei,
    ShardNumber,
    SlotNumber,
    Timestamp,
    ValidatorIndex,
)
from eth2.beacon.validator_status_helpers import (
    activate_validator,
)


def get_genesis_block(startup_state_root: Hash32,
                      genesis_slot: SlotNumber,
                      block_class: Type[BaseBeaconBlock]) -> BaseBeaconBlock:
    return block_class(
        slot=genesis_slot,
        parent_root=ZERO_HASH32,
        state_root=startup_state_root,
        randao_reveal=ZERO_HASH32,
        eth1_data=Eth1Data.create_empty_data(),
        signature=EMPTY_SIGNATURE,
        body=BeaconBlockBody.create_empty_body(),
    )


def get_initial_beacon_state(*,
                             initial_validator_deposits: Sequence[Deposit],
                             genesis_time: Timestamp,
                             latest_eth1_data: Eth1Data,
                             genesis_slot: SlotNumber,
                             genesis_epoch: EpochNumber,
                             genesis_fork_version: int,
                             genesis_start_shard: ShardNumber,
                             shard_count: int,
                             seed_lookahead: int,
                             latest_block_roots_length: int,
                             latest_index_roots_length: int,
                             epoch_length: int,
                             max_deposit_amount: Gwei,
                             latest_penalized_exit_length: int,
                             latest_randao_mixes_length: int,
                             entry_exit_delay: int) -> BeaconState:
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
        latest_randao_mixes=tuple(ZERO_HASH32 for _ in range(latest_randao_mixes_length)),
        previous_epoch_start_shard=genesis_start_shard,
        current_epoch_start_shard=genesis_start_shard,
        previous_calculation_epoch=genesis_epoch,
        current_calculation_epoch=genesis_epoch,
        previous_epoch_seed=ZERO_HASH32,
        current_epoch_seed=ZERO_HASH32,

        # Finality
        previous_justified_epoch=genesis_epoch,
        justified_epoch=genesis_epoch,
        justification_bitfield=0,
        finalized_epoch=genesis_epoch,

        # Recent state
        latest_crosslinks=tuple([
            CrosslinkRecord(epoch=genesis_epoch, shard_block_root=ZERO_HASH32)
            for _ in range(shard_count)
        ]),
        latest_block_roots=tuple(ZERO_HASH32 for _ in range(latest_block_roots_length)),
        latest_index_roots=tuple(ZERO_HASH32 for _ in range(latest_index_roots_length)),
        latest_penalized_balances=tuple(
            Gwei(0)
            for _ in range(latest_penalized_exit_length)
        ),
        latest_attestations=(),
        batched_block_roots=(),

        # Ethereum 1.0 chain data
        latest_eth1_data=latest_eth1_data,
        eth1_data_votes=(),
    )

    # Process initial deposits
    for deposit in initial_validator_deposits:
        state = process_deposit(
            state=state,
            pubkey=deposit.deposit_data.deposit_input.pubkey,
            amount=deposit.deposit_data.amount,
            proof_of_possession=deposit.deposit_data.deposit_input.proof_of_possession,
            withdrawal_credentials=deposit.deposit_data.deposit_input.withdrawal_credentials,
            randao_commitment=deposit.deposit_data.deposit_input.randao_commitment,
            epoch_length=epoch_length,
        )

    # Process initial activations
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
                epoch_length=epoch_length,
                entry_exit_delay=entry_exit_delay,
            )

    # TODO: chanege to hash_tree_root
    active_validator_indices = get_active_validator_indices(
        state.validator_registry,
        genesis_epoch,
    )
    index_root = hash_eth2(
        b''.join(
            [
                index.to_bytes(32, 'big')
                for index in active_validator_indices
            ]
        )
    )
    latest_index_roots = update_tuple_item(
        state.latest_index_roots,
        genesis_epoch % latest_index_roots_length,
        index_root,
    )
    state = state.copy(
        latest_index_roots=latest_index_roots,
    )

    current_epoch_seed = generate_seed(
        state=state,
        epoch=genesis_epoch,
        epoch_length=epoch_length,
        seed_lookahead=seed_lookahead,
        entry_exit_delay=entry_exit_delay,
        latest_index_roots_length=latest_index_roots_length,
        latest_randao_mixes_length=latest_randao_mixes_length,
    )
    state = state.copy(
        current_epoch_seed=current_epoch_seed,
    )

    return state
