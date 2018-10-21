from eth_typing import (
    BlockNumber,
)


class SyncProgress:
    def __init__(self,
                 starting_block: BlockNumber = None,
                 current_block: BlockNumber = None,
                 highest_block: BlockNumber = None) -> None:
        self.starting_block = starting_block
        self.current_block = current_block
        self.highest_block = highest_block
