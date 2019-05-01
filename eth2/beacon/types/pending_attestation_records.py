import ssz
from ssz.sedes import (
    bytes_sedes,
    uint64,
)

from eth2.beacon.typing import (
    Slot,
    Bitfield,
)

from .attestation_data import (
    AttestationData,
)


class PendingAttestationRecord(ssz.Serializable):

    fields = [
        # Attester aggregation bitfield
        ('aggregation_bitfield', bytes_sedes),
        # Attestation data
        ('data', AttestationData),
        # Custody bitfield
        ('custody_bitfield', bytes_sedes),
        # Inclusion slot
        ('inclusion_slot', uint64),
    ]

    def __init__(self,
                 aggregation_bitfield: Bitfield,
                 data: AttestationData,
                 custody_bitfield: Bitfield,
                 inclusion_slot: Slot) -> None:
        super().__init__(
            aggregation_bitfield=aggregation_bitfield,
            data=data,
            custody_bitfield=custody_bitfield,
            inclusion_slot=inclusion_slot,
        )
