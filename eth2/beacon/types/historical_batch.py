from typing import (
    Sequence,
)

from eth_typing import (
    Hash32,
)

import ssz
from ssz.sedes import (
    bytes32,
    List,
)


class HistoricalBatch(ssz.Serializable):

    fields = [
        # Block roots
        ('block_roots', List(bytes32)),
        # State roots
        ('state_roots', List(bytes32)),
    ]

    def __init__(self,
                 *,
                 block_roots: Sequence[Hash32],
                 state_roots: Sequence[Hash32],
                 slots_per_historical_root: int) -> None:
        assert len(block_roots) == slots_per_historical_root
        assert len(state_roots) == slots_per_historical_root

        super().__init__(
            block_roots=block_roots,
            state_roots=state_roots,
        )

    _hash_tree_root = None

    @property
    def hash_tree_root(self) -> Hash32:
        if self._hash_tree_root is None:
            self._hash_tree_root = ssz.hash_tree_root(self)
        return self._hash_tree_root
