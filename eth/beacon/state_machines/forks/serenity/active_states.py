from eth.beacon.types.active_states import ActiveState
from eth.beacon.helpers import (
    get_new_recent_block_hashes,
)


class SerenityActiveState(ActiveState):
    @classmethod
    def from_old_active_and_blocks(cls, old_active_state, blocks, recent_block_hashes_length):
        recent_block_hashes = old_active_state.recent_block_hashes
        pending_attestations = old_active_state.pending_attestations

        index = 0
        while index < len(blocks) - 1:
            recent_block_hashes = get_new_recent_block_hashes(
                old_block_hashes=recent_block_hashes,
                parent_slot=blocks[index].slot_number,
                current_slot=blocks[index + 1].slot_number,
                parent_hash=blocks[index].hash
            )
            pending_attestations += blocks[index].attestations
            index += 1

        return cls(
            recent_block_hashes=recent_block_hashes,
            pending_attestations=pending_attestations,
        )
