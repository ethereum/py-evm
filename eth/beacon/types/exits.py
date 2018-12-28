import rlp
from rlp.sedes import (
    CountableList,
)
from eth.rlp.sedes import (
    uint24,
    uint64,
    uint384,
)
from eth.beacon.typing import (
    BLSSignature,
    SlotNumber,
    ValidatorIndex,
)
from eth.beacon.constants import EMPTY_SIGNATURE


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
                 slot: SlotNumber,
                 validator_index: ValidatorIndex,
                 signature: BLSSignature=EMPTY_SIGNATURE) -> None:
        super().__init__(
            slot,
            validator_index,
            signature,
        )
