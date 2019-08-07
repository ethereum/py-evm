import ssz
from ssz.sedes import (
    bytes4,
    bytes32,
    uint64,
)

from eth2.beacon.typing import (  # noqa: F401
    default_epoch,
    default_slot,
    default_version,
)

# # ErrorMessage
# (
#   error_message: String
# )


# # HelloRequest
# (
#   fork_version: bytes4
#   finalized_root: bytes32
#   finalized_epoch: uint64
#   head_root: bytes32
#   head_slot: uint64
# )
class HelloRequest(ssz.Serializable):
    fields = [
        ('fork_version', bytes4),
        ('finalized_root', bytes32),
        ('finalized_epoch', uint64),
        ('head_root', bytes32),
        ('head_slot', uint64)
    ]

    def __init__(
        self,
        fork_version: bytes,
        finalized_root: bytes,
        finalized_epoch: int,
        head_root: bytes,
        head_slot: int
    ) -> None:
        super().__init__(
            fork_version,
            finalized_root,
            finalized_epoch,
            head_root,
            head_slot,
        )


# # TODO: Goodbye
# (
#   reason: uint64
# )


# # TODO: BeaconBlocksRequest
# (
#   head_block_root: HashTreeRoot
#   start_slot: uint64
#   count: uint64
#   step: uint64
# )
# # BeaconBlocksResponse
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
