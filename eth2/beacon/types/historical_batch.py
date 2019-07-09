from typing import (
    Sequence,
)

from eth.constants import (
    ZERO_HASH32,
)
from eth_typing import (
    Hash32,
)

import ssz
from ssz.sedes import (
    bytes32,
    Vector,
)

from eth2.configs import (
    Eth2Config,
)

from .defaults import (
    default_tuple,
    default_tuple_of_size,
)


class HistoricalBatch(ssz.Serializable):

    fields = [
        ('block_roots', Vector(bytes32, 1)),
        ('state_roots', Vector(bytes32, 1)),
    ]

    def __init__(self,
                 *,
                 block_roots: Sequence[Hash32]=default_tuple,
                 state_roots: Sequence[Hash32]=default_tuple,
                 config: Eth2Config=None) -> None:
        if config:
            # try to provide sane defaults
            if block_roots == default_tuple:
                block_roots = default_tuple_of_size(config.SLOTS_PER_HISTORICAL_ROOT, ZERO_HASH32)
            if state_roots == default_tuple:
                state_roots = default_tuple_of_size(config.SLOTS_PER_HISTORICAL_ROOT, ZERO_HASH32)

        super().__init__(
            block_roots=block_roots,
            state_roots=state_roots,
        )
