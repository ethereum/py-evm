import ssz
from ssz.sedes import (
    bytes96,
    uint64,
)

from eth2.beacon.typing import (
    BLSSignature,
    EpochNumber,
    ValidatorIndex,
)
from eth2.beacon.constants import EMPTY_SIGNATURE


class VoluntaryExit(ssz.Serializable):

    fields = [
        # Minimum epoch for processing exit
        ('epoch', uint64),
        # Index of the exiting validator
        ('validator_index', uint64),
        # Validator signature
        ('signature', bytes96),
    ]

    def __init__(self,
                 epoch: EpochNumber,
                 validator_index: ValidatorIndex,
                 signature: BLSSignature=EMPTY_SIGNATURE) -> None:
        super().__init__(
            epoch,
            validator_index,
            signature,
        )
