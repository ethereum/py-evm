
from typing import (
    Sequence,
    TYPE_CHECKING,
)

from eth.beacon.types.active_states import ActiveState
from eth.beacon.helpers import (
    get_new_recent_block_hashes,
)

if TYPE_CHECKING:
    from eth.beacon.types.blocks import BaseBeaconBlock  # noqa: F401


class SerenityActiveState(ActiveState):
    @classmethod
    def from_backup_active_state_and_blocks(cls,
                                            backup_active_state: ActiveState,
                                            blocks: Sequence['BaseBeaconBlock']) -> ActiveState:
        # NOTE: The following logic in beacon chain spec will be changed with the current spec.
        recent_block_hashes = backup_active_state.recent_block_hashes
        pending_attestations = backup_active_state.pending_attestations

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
