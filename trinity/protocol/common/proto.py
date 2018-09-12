from typing import NamedTuple

from eth_typing import (
    BlockNumber,
    Hash32,
)


class ChainInfo(NamedTuple):
    block_number: BlockNumber
    block_hash: Hash32
    total_difficulty: int
    genesis_hash: Hash32
