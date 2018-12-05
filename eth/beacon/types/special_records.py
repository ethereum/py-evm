import rlp
from rlp.sedes import (
    binary,
)

from eth.rlp.sedes import (
    uint64,
)


class SpecialRecord(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Kind
        ('kind', uint64),
        # Data
        ('data', binary),
    ]

    def __init__(self,
                 kind: int,
                 data: bytes) -> None:
        super().__init__(
            kind=kind,
            data=data,
        )
