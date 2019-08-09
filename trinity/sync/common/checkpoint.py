from typing import NamedTuple

from eth_typing import (
    Hash32,
)
from eth_utils import (
    humanize_hash
)


class Checkpoint(NamedTuple):
    """
    Represent a checkpoint from where the syncing process can start off
    when not starting from genesis.
    """
    block_hash: Hash32
    score: int

    def __str__(self) -> str:
        return (
            f"<Checkpoint block hash=#{humanize_hash(self.block_hash)}"
            f" score={self.score}>"
        )
