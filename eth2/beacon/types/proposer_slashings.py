import ssz
from ssz.sedes import (
    uint64,
)

from .block_headers import BeaconBlockHeader
from eth2.beacon.typing import (
    ValidatorIndex,
)


class ProposerSlashing(ssz.Serializable):

    fields = [
        # Proposer index
        ('proposer_index', uint64),
        # First block header
        ('header_1', BeaconBlockHeader),
        # Second block header
        ('header_2', BeaconBlockHeader),
    ]

    def __init__(self,
                 proposer_index: ValidatorIndex,
                 header_1: BeaconBlockHeader,
                 header_2: BeaconBlockHeader) -> None:
        super().__init__(
            proposer_index=proposer_index,
            header_1=header_1,
            header_2=header_2,
        )
