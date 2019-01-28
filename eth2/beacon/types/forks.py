import rlp

from eth2.beacon.sedes import (
    uint64,
)

from eth2.beacon.typing import (
    SlotNumber,
)


class Fork(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Previous fork version
        ('previous_version', uint64),
        # Current fork version
        ('current_version', uint64),
        # Fork slot number
        ('slot', uint64)
    ]

    def __init__(self,
                 previous_version: int,
                 current_version: int,
                 slot: SlotNumber) -> None:
        super().__init__(
            previous_version=previous_version,
            current_version=current_version,
            slot=slot,
        )
