import ssz
from ssz.sedes import (
    bytes4,
    bytes32,
    uint64,
)

from eth_typing import (
    Hash32,
)

from eth.constants import (
    ZERO_HASH32,
)

from eth2.beacon.typing import (
    Version,
    default_epoch,
    default_slot,
    default_version,
)


class HelloRequest(ssz.Serializable):
    fields = [
        ('fork_version', bytes4),
        ('finalized_root', bytes32),
        ('finalized_epoch', uint64),
        ('head_root', bytes32),
        ('head_slot', uint64),
    ]

    def __init__(
        self,
        fork_version: Version = default_version,
        finalized_root: Hash32 = ZERO_HASH32,
        finalized_epoch: int = default_epoch,
        head_root: Hash32 = ZERO_HASH32,
        head_slot: int = default_slot,
    ) -> None:
        super().__init__(
            fork_version,
            finalized_root,
            finalized_epoch,
            head_root,
            head_slot,
        )


class Goodbye(ssz.Serializable):
    fields = [
        ('reason', uint64),
    ]

    def __init__(self, reason: int) -> None:
        super().__init__(reason)


class BeaconBlocksRequest(ssz.Serializable):
    fields = [
        ('head_block_root', bytes32),
        ('start_slot', uint64),
        ('count', uint64),
        ('step', uint64),
    ]

    def __init__(
        self,
        head_block_root: bytes,
        start_slot: int,
        count: int,
        step: int,
    ) -> None:
        super().__init__(
            head_block_root,
            start_slot,
            count,
            step,
        )


# # TODO: BeaconBlocksResponse
# (
#   blocks: []BeaconBlock
# )


# # TODO: RecentBeaconBlocksRequest
# (
#   block_roots: []HashTreeRoot
# )

# # RecentBeaconBlocksResponse
# (
#   blocks: []BeaconBlock
# )
