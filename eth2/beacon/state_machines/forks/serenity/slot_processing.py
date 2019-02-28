from eth_typing import (
    Hash32,
)

from eth2._utils.merkle import get_merkle_root
from eth2.beacon.configs import (
    BeaconConfig,
)
from eth2.beacon.types.states import BeaconState


def process_slot_transition(state: BeaconState,
                            config: BeaconConfig,
                            previous_block_root: Hash32) -> BeaconState:
    latest_block_roots_length = config.LATEST_BLOCK_ROOTS_LENGTH

    # Update state.slot
    state = state.copy(
        slot=state.slot + 1
    )

    # Update state.latest_block_roots
    updated_latest_block_roots = list(state.latest_block_roots)
    previous_block_root_index = (state.slot - 1) % latest_block_roots_length
    updated_latest_block_roots[previous_block_root_index] = previous_block_root

    # Update state.batched_block_roots
    updated_batched_block_roots = state.batched_block_roots
    if state.slot % latest_block_roots_length == 0:
        updated_batched_block_roots += (get_merkle_root(updated_latest_block_roots),)

    state = state.copy(
        latest_block_roots=tuple(updated_latest_block_roots),
        batched_block_roots=updated_batched_block_roots,
    )

    return state
