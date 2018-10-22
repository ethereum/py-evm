from typing import (
    NamedTuple,
)

from eth_typing import (
    BlockNumber,
)


class SyncProgress(NamedTuple):
    starting_block: BlockNumber
    current_block: BlockNumber
    highest_block: BlockNumber

    def update_current_block(self, new_current_block: BlockNumber) -> 'SyncProgress':
        return SyncProgress(self.starting_block, new_current_block, self.highest_block)
