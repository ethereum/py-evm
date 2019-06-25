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
        ('previous_version', bytes4),
        ('current_version', bytes4),
        # Epoch of latest fork
        ('epoch', uint64)
    ]

    def __init__(self,
                 previous_version: bytes=b'\x00' * 4,
                 current_version: bytes=b'\x00' * 4,
                 epoch: Epoch=0) -> None:
        super().__init__(
            previous_version=previous_version,
            current_version=current_version,
            epoch=epoch,
        )
