from eth_typing import (
    Hash32,
)

from eth2._utils.merkle.normal import get_merkle_root
from eth2.beacon.configs import (
    BeaconConfig,
)
from eth2.beacon.types.states import BeaconState


def process_slot_transition(state: BeaconState,
                            config: BeaconConfig,
                            previous_block_root: Hash32) -> BeaconState:
    slots_per_historical_root = config.SLOTS_PER_HISTORICAL_ROOT

    # Update state.slot
    state = state.copy(
        slot=state.slot + 1
    )

    # Update state.latest_block_roots
    updated_latest_block_roots = list(state.latest_block_roots)
    previous_block_root_index = (state.slot - 1) % slots_per_historical_root
    updated_latest_block_roots[previous_block_root_index] = previous_block_root

    # Update state.batched_block_roots
    updated_batched_block_roots = state.batched_block_roots
    if state.slot % slots_per_historical_root == 0:
        updated_batched_block_roots += (get_merkle_root(updated_latest_block_roots),)

    state = state.copy(
        latest_block_roots=tuple(updated_latest_block_roots),
        batched_block_roots=updated_batched_block_roots,
    )

    return state
