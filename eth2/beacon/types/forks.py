import ssz
from ssz.sedes import (
    bytes4,
    uint64,
)

from eth2.beacon.typing import (
    Epoch,
)


class Fork(ssz.Serializable):

    fields = [
        # Previous fork version
        ('previous_version', bytes4),
        # Current fork version
        ('current_version', bytes4),
        # Fork epoch number
        ('epoch', uint64)
    ]

    def __init__(self,
                 previous_version: bytes,
                 current_version: bytes,
                 epoch: Epoch) -> None:
        super().__init__(
            previous_version=previous_version,
            current_version=current_version,
            epoch=epoch,
        )
