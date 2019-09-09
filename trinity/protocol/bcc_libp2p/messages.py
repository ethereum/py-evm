from typing import (
    Sequence,
)

import ssz
from ssz.sedes import (
    List,
    bytes4,
    bytes32,
    uint64,
)

from eth2.beacon.typing import (
    Version,
    default_epoch,
    default_slot,
    default_version,
)
from eth2.beacon.types.blocks import BeaconBlock
from eth2.beacon.typing import SigningRoot, HashTreeRoot, Slot, Epoch
from eth2.beacon.constants import (
    ZERO_HASH_TREE_ROOT,
    ZERO_SIGNING_ROOT,
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
        finalized_root: SigningRoot = ZERO_SIGNING_ROOT,
        finalized_epoch: Epoch = default_epoch,
        head_root: HashTreeRoot = ZERO_HASH_TREE_ROOT,
        head_slot: Slot = default_slot,
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
        head_block_root: HashTreeRoot,
        start_slot: Slot,
        count: int,
        step: int,
    ) -> None:
        super().__init__(
            head_block_root,
            start_slot,
            count,
            step,
        )


class BeaconBlocksResponse(ssz.Serializable):
    fields = [
        ('blocks', List(BeaconBlock, 1)),
    ]

    def __init__(self, blocks: Sequence[BeaconBlock]) -> None:
        super().__init__(blocks)


class RecentBeaconBlocksRequest(ssz.Serializable):
    fields = [
        ('block_roots', List(bytes32, 1)),
    ]

    def __init__(self, block_roots: Sequence[HashTreeRoot]) -> None:
        super().__init__(block_roots)


class RecentBeaconBlocksResponse(ssz.Serializable):
    fields = [
        ('blocks', List(BeaconBlock, 1)),
    ]

    def __init__(self, blocks: Sequence[BeaconBlock]) -> None:
        super().__init__(blocks)
