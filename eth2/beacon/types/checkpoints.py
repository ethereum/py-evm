from eth_typing import (
    Hash32,
)

from eth.constants import (
    ZERO_HASH32,
)

import ssz
from ssz.sedes import (
    bytes32,
    uint64,
)

from eth2.beacon.typing import (
    Epoch,
)

from .defaults import (
    default_epoch,
)


class Checkpoint(ssz.Serializable):

    fields = [
        ('epoch', uint64),
        ('root', bytes32)
    ]

    def __init__(self,
                 epoch: Epoch=default_epoch,
                 root: Hash32=ZERO_HASH32) -> None:
        super().__init__(
            epoch=epoch,
            root=root,
        )


default_checkpoint = Checkpoint()
