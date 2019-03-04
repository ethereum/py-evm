from typing import (
    NamedTuple,
)

from eth_typing import (
    Hash32,
)

from eth2.beacon.typing import (
    Epoch,
    Shard,
)


class ShufflingContext(NamedTuple):
    committees_per_epoch: int
    seed: Hash32
    shuffling_epoch: Epoch
    shuffling_start_shard: Shard
