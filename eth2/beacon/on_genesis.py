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
import ssz

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
from eth2.beacon.types.crosslinks import Crosslink
from eth2.beacon.types.deposits import Deposit
from eth2.beacon.types.eth1_data import Eth1Data
from eth2.beacon.types.forks import Fork
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    Gwei,
    Slot,
    Timestamp,
    ValidatorIndex,
)
from eth2.beacon.validator_status_helpers import (
    activate_validator,
)
from eth2.configs import (
    Eth2Config,
    CommitteeConfig,
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
                             config: Eth2Config) -> BeaconState:
    state = BeaconState(
        # Misc
        slot=config.GENESIS_SLOT,
        genesis_time=genesis_time,
        fork=Fork(
            previous_version=config.GENESIS_FORK_VERSION.to_bytes(4, 'little'),
            current_version=config.GENESIS_FORK_VERSION.to_bytes(4, 'little'),
            epoch=config.GENESIS_EPOCH,
        ),

        # Validator registry
        validator_registry=(),
        validator_balances=(),
        validator_registry_update_epoch=config.GENESIS_EPOCH,

        # Randomness and committees
        latest_randao_mixes=(ZERO_HASH32,) * config.LATEST_RANDAO_MIXES_LENGTH,
        previous_shuffling_start_shard=config.GENESIS_START_SHARD,
        current_shuffling_start_shard=config.GENESIS_START_SHARD,
        previous_shuffling_epoch=config.GENESIS_EPOCH,
        current_shuffling_epoch=config.GENESIS_EPOCH,
        previous_shuffling_seed=ZERO_HASH32,
        current_shuffling_seed=ZERO_HASH32,

        # Finality
        previous_epoch_attestations=(),
        current_epoch_attestations=(),
        previous_justified_epoch=config.GENESIS_EPOCH,
        current_justified_epoch=config.GENESIS_EPOCH,
        previous_justified_root=ZERO_HASH32,
        current_justified_root=ZERO_HASH32,
        justification_bitfield=0,
        finalized_epoch=config.GENESIS_EPOCH,
        finalized_root=ZERO_HASH32,

        # Recent state
        latest_crosslinks=(
            (
                Crosslink(
                    epoch=config.GENESIS_EPOCH,
                    crosslink_data_root=ZERO_HASH32,
                ),
            ) * config.SHARD_COUNT
        ),
        latest_block_roots=(ZERO_HASH32,) * config.SLOTS_PER_HISTORICAL_ROOT,
        latest_state_roots=(ZERO_HASH32,) * config.SLOTS_PER_HISTORICAL_ROOT,
        latest_active_index_roots=(ZERO_HASH32,) * config.LATEST_ACTIVE_INDEX_ROOTS_LENGTH,
        latest_slashed_balances=(Gwei(0),) * config.LATEST_SLASHED_EXIT_LENGTH,
        latest_block_header=get_temporary_block_header(
            BeaconBlock.create_empty_block(config.GENESIS_SLOT),
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
            slots_per_epoch=config.SLOTS_PER_EPOCH,
            deposit_contract_tree_depth=config.DEPOSIT_CONTRACT_TREE_DEPTH,
        )

    # Process genesis activations
    for validator_index, _ in enumerate(state.validator_registry):
        validator_index = ValidatorIndex(validator_index)
        is_enough_effective_balance = get_effective_balance(
            state.validator_balances,
            validator_index,
            config.MAX_DEPOSIT_AMOUNT,
        ) >= config.MAX_DEPOSIT_AMOUNT
        if is_enough_effective_balance:
            state = activate_validator(
                state=state,
                index=validator_index,
                is_genesis=True,
                genesis_epoch=config.GENESIS_EPOCH,
                slots_per_epoch=config.SLOTS_PER_EPOCH,
                activation_exit_delay=config.ACTIVATION_EXIT_DELAY,
            )

    active_validator_indices = get_active_validator_indices(
        state.validator_registry,
        config.GENESIS_EPOCH,
    )
    genesis_active_index_root = ssz.hash_tree_root(
        active_validator_indices,
        ssz.sedes.List(ssz.uint64),
    )
    latest_active_index_roots = (
        (genesis_active_index_root,) * config.LATEST_ACTIVE_INDEX_ROOTS_LENGTH
    )
    state = state.copy(
        latest_active_index_roots=latest_active_index_roots,
    )

    current_shuffling_seed = generate_seed(
        state=state,
        epoch=config.GENESIS_EPOCH,
        committee_config=CommitteeConfig(config),
    )
    state = state.copy(
        current_shuffling_seed=current_shuffling_seed,
    )

    return state
