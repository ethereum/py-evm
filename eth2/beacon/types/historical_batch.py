from typing import (
    Sequence,
)

from eth_typing import (
    Hash32,
)

import ssz
from ssz.sedes import (
    bytes32,
    Vector,
)


class HistoricalBatch(ssz.Serializable):

    fields = [
        # Block roots
        ('block_roots', Vector(bytes32, 1)),
        # State roots
        ('state_roots', Vector(bytes32, 1)),
    ]

    def __init__(self,
                 *,
                 block_roots: Sequence[Hash32],
                 state_roots: Sequence[Hash32]) -> None:
        super().__init__(
            block_roots=block_roots,
            state_roots=state_roots,
        )
