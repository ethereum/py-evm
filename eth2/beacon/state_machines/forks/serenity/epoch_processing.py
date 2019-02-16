from typing import (
    Iterable,
    Sequence,
    Tuple,
)

from eth_utils import to_tuple

from eth2.beacon import helpers
from eth2._utils.numeric import (
    is_power_of_two,
)
from eth2._utils.tuple import (
    update_tuple_item,
)
from eth2.beacon.exceptions import (
    NoWinningRootError,
)
from eth2.beacon.committee_helpers import (
    get_crosslink_committees_at_slot,
    get_current_epoch_committee_count,
)
from eth2.beacon.configs import (
    BeaconConfig,
    CommitteeConfig,
)
from eth2.beacon.epoch_processing_helpers import (
    get_current_epoch_attestations,
    get_previous_epoch_attestations,
    get_winning_root,
)
from eth2.beacon.helpers import (
    get_active_validator_indices,
    get_effective_balance,
    get_epoch_start_slot,
    get_randao_mix,
    slot_to_epoch,
)
from eth2.beacon.typing import ShardNumber
from eth2.beacon._utils.hash import (
    hash_eth2,
)
from eth2.beacon.types.attestations import Attestation
from eth2.beacon.types.crosslink_records import CrosslinkRecord
from eth2.beacon.types.states import BeaconState
from eth2.beacon.typing import (
    EpochNumber,
)


#
# Crosslinks
#
@to_tuple
def _filter_attestations_by_shard(
        attestations: Sequence[Attestation],
        shard: ShardNumber) -> Iterable[Attestation]:
    for attestation in attestations:
        if attestation.data.shard == shard:
            yield attestation


def process_crosslinks(state: BeaconState, config: BeaconConfig) -> BeaconState:
    """
    Implement 'per-epoch-processing.crosslinks' portion of Phase 0 spec:
    https://github.com/ethereum/eth2.0-specs/blob/master/specs/core/0_beacon-chain.md#crosslinks

    For each shard from the past two epochs, find the shard block
    root that has been attested to by the most stake.
    If enough(>= 2/3 total stake) attesting stake, update the crosslink record of that shard.
    Return resulting ``state``
    """
    latest_crosslinks = state.latest_crosslinks
    previous_epoch_attestations = get_previous_epoch_attestations(
        state,
        config.EPOCH_LENGTH,
        config.GENESIS_EPOCH,
    )
    current_epoch_attestations = get_current_epoch_attestations(state, config.EPOCH_LENGTH)
    prev_epoch_start_slot = get_epoch_start_slot(
        state.previous_epoch(config.EPOCH_LENGTH, config.GENESIS_EPOCH),
        config.EPOCH_LENGTH,
    )
    next_epoch_start_slot = get_epoch_start_slot(
        state.next_epoch(config.EPOCH_LENGTH),
        config.EPOCH_LENGTH,
    )
    for slot in range(prev_epoch_start_slot, next_epoch_start_slot):
        crosslink_committees_at_slot = get_crosslink_committees_at_slot(
            state,
            slot,
            CommitteeConfig(config),
        )
        for crosslink_committee, shard in crosslink_committees_at_slot:
            try:
                winning_root, total_attesting_balance = get_winning_root(
                    state=state,
                    shard=shard,
                    # Use `_filter_attestations_by_shard` to filter out attestations
                    # not attesting to this shard so we don't need to going over
                    # irrelevent attestations over and over again.
                    attestations=_filter_attestations_by_shard(
                        previous_epoch_attestations + current_epoch_attestations,
                        shard,
                    ),
                    max_deposit_amount=config.MAX_DEPOSIT_AMOUNT,
                    committee_config=CommitteeConfig(config),
                )
            except NoWinningRootError:
                # No winning shard block root found for this shard.
                pass
            else:
                total_balance = sum(
                    get_effective_balance(state.validator_balances, i, config.MAX_DEPOSIT_AMOUNT)
                    for i in crosslink_committee
                )
                if 3 * total_attesting_balance >= 2 * total_balance:
                    latest_crosslinks = update_tuple_item(
                        latest_crosslinks,
                        shard,
                        CrosslinkRecord(
                            epoch=state.current_epoch(config.EPOCH_LENGTH),
                            shard_block_root=winning_root,
                        ),
                    )
                else:
                    # Don't update the crosslink of this shard
                    pass
    state = state.copy(
        latest_crosslinks=latest_crosslinks,
    )
    return state


#
# Validator registry and shuffling seed data
#
def _check_if_update_validator_registry(state: BeaconState,
                                        config: BeaconConfig) -> Tuple[bool, int]:
    if state.finalized_epoch <= state.validator_registry_update_epoch:
        return False, 0

    num_shards_in_committees = get_current_epoch_committee_count(
        state,
        shard_count=config.SHARD_COUNT,
        epoch_length=config.EPOCH_LENGTH,
        target_committee_size=config.TARGET_COMMITTEE_SIZE,
    )

    # Get every shard in the current committees
    shards = set(
        (state.current_epoch_start_shard + i) % config.SHARD_COUNT
        for i in range(num_shards_in_committees)
    )
    for shard in shards:
        if state.latest_crosslinks[shard].epoch <= state.validator_registry_update_epoch:
            return False, 0

    return True, num_shards_in_committees


def update_validator_registry(state: BeaconState) -> BeaconState:
    # TODO
    return state


def process_validator_registry(state: BeaconState,
                               config: BeaconConfig) -> BeaconState:
    state = state.copy(
        previous_calculation_epoch=state.current_calculation_epoch,
        previous_epoch_start_shard=state.current_epoch_start_shard,
        previous_epoch_seed=state.current_epoch_seed,
    )

    need_to_update, num_shards_in_committees = _check_if_update_validator_registry(state, config)

    if need_to_update:
        state = update_validator_registry(state)

        # Update step-by-step since updated `state.current_calculation_epoch`
        # is used to calculate other value). Follow the spec tightly now.
        state = state.copy(
            current_calculation_epoch=state.next_epoch(config.EPOCH_LENGTH),
        )
        state = state.copy(
            current_epoch_start_shard=(
                state.current_epoch_start_shard + num_shards_in_committees
            ) % config.SHARD_COUNT,
        )

        # The `helpers.generate_seed` function is only present to provide an entry point
        # for mocking this out in tests.
        current_epoch_seed = helpers.generate_seed(
            state=state,
            epoch=state.current_calculation_epoch,
            epoch_length=config.EPOCH_LENGTH,
            seed_lookahead=config.SEED_LOOKAHEAD,
            entry_exit_delay=config.ENTRY_EXIT_DELAY,
            latest_index_roots_length=config.LATEST_INDEX_ROOTS_LENGTH,
            latest_randao_mixes_length=config.LATEST_RANDAO_MIXES_LENGTH,
        )
        state = state.copy(
            current_epoch_seed=current_epoch_seed,
        )
    else:
        epochs_since_last_registry_change = (
            state.current_epoch(config.EPOCH_LENGTH) - state.validator_registry_update_epoch
        )
        if is_power_of_two(epochs_since_last_registry_change):
            # Update step-by-step since updated `state.current_calculation_epoch`
            # is used to calculate other value). Follow the spec tightly now.
            state = state.copy(
                current_calculation_epoch=state.next_epoch(config.EPOCH_LENGTH),
            )

            # The `helpers.generate_seed` function is only present to provide an entry point
            # for mocking this out in tests.
            current_epoch_seed = helpers.generate_seed(
                state=state,
                epoch=state.current_calculation_epoch,
                epoch_length=config.EPOCH_LENGTH,
                seed_lookahead=config.SEED_LOOKAHEAD,
                entry_exit_delay=config.ENTRY_EXIT_DELAY,
                latest_index_roots_length=config.LATEST_INDEX_ROOTS_LENGTH,
                latest_randao_mixes_length=config.LATEST_RANDAO_MIXES_LENGTH,
            )
            state = state.copy(
                current_epoch_seed=current_epoch_seed,
            )
        else:
            pass

    return state


#
# Final updates
#
def _update_latest_index_roots(state: BeaconState,
                               committee_config: CommitteeConfig) -> BeaconState:
    """
    Return the BeaconState with updated `latest_index_roots`.
    """
    next_epoch = state.next_epoch(committee_config.EPOCH_LENGTH)

    # TODO: chanege to hash_tree_root
    active_validator_indices = get_active_validator_indices(
        state.validator_registry,
        EpochNumber(next_epoch + committee_config.ENTRY_EXIT_DELAY),
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
        (
            (next_epoch + committee_config.ENTRY_EXIT_DELAY) %
            committee_config.LATEST_INDEX_ROOTS_LENGTH
        ),
        index_root,
    )

    return state.copy(
        latest_index_roots=latest_index_roots,
    )


def process_final_updates(state: BeaconState,
                          config: BeaconConfig) -> BeaconState:
    current_epoch = state.current_epoch(config.EPOCH_LENGTH)
    next_epoch = state.next_epoch(config.EPOCH_LENGTH)

    state = _update_latest_index_roots(state, CommitteeConfig(config))

    state = state.copy(
        latest_penalized_balances=update_tuple_item(
            state.latest_penalized_balances,
            next_epoch % config.LATEST_PENALIZED_EXIT_LENGTH,
            state.latest_penalized_balances[current_epoch % config.LATEST_PENALIZED_EXIT_LENGTH],
        ),
        latest_randao_mixes=update_tuple_item(
            state.latest_randao_mixes,
            next_epoch % config.LATEST_PENALIZED_EXIT_LENGTH,
            get_randao_mix(
                state=state,
                epoch=current_epoch,
                epoch_length=config.EPOCH_LENGTH,
                latest_randao_mixes_length=config.LATEST_RANDAO_MIXES_LENGTH,
            ),
        ),
    )

    latest_attestations = tuple(
        filter(
            lambda attestation: (
                slot_to_epoch(attestation.data.slot, config.EPOCH_LENGTH) >= current_epoch
            ),
            state.latest_attestations
        )
    )
    state = state.copy(
        latest_attestations=latest_attestations,
    )

    return state
