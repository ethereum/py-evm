from typing import Sequence
import rlp
from rlp.sedes import (
    CountableList,
)
from eth.rlp.sedes import (
    uint24,
    uint64,
    uint384,
)


class Exit(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Minimum slot for processing exit
        ('slot', uint64),
        # Index of the exiting validator
        ('validator_index', uint24),
        # Validator signature
        ('signature', CountableList(uint384)),
    ]

    def __init__(self,
                 slot: int,
                 validator_index: int,
                 signature: Sequence[int]) -> None:
        super().__init__(
            slot,
            validator_index,
            signature,
        )
