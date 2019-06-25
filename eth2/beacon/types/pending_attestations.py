import ssz
from ssz.sedes import (
    byte_list,
    uint64,
)

from eth2.beacon.typing import (
    Bitfield,
    ValidatorIndex,
)

from .attestation_data import (
    AttestationData,
)


class PendingAttestation(ssz.Serializable):

    fields = [
        ('aggregation_bitfield', byte_list),
        ('data', AttestationData),
        ('inclusion_delay', uint64),
        ('proposer_index', uint64),
    ]

    def __init__(self,
                 aggregation_bitfield: Bitfield=Bitfield(),
                 data: AttestationData=AttestationData(),
                 inclusion_delay: int=0,
                 proposer_index: ValidatorIndex=ValidatorIndex(0)) -> None:
        super().__init__(
            aggregation_bitfield=aggregation_bitfield,
            data=data,
            inclusion_delay=inclusion_delay,
            proposer_index=proposer_index,
        )

    def __repr__(self) -> str:
        return f"<PendingAttestation inclusion_slot={self.inclusion_slot} data={self.data}>"
