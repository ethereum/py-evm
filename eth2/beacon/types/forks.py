import ssz
from ssz.sedes import (
    uint64,
)

from eth2.beacon.typing import (
    EpochNumber,
)


class Fork(ssz.Serializable):

    fields = [
        # Previous fork version
        ('previous_version', uint64),
        # Current fork version
        ('current_version', uint64),
        # Fork epoch number
        ('epoch', uint64)
    ]

    def __init__(self,
                 previous_version: int,
                 current_version: int,
                 epoch: EpochNumber) -> None:
        super().__init__(
            previous_version=previous_version,
            current_version=current_version,
            epoch=epoch,
        )
