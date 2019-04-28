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
        # Signed data
        ('data', AttestationData),
        # Attester aggregation bitfield
        ('aggregation_bitfield', bytes_sedes),
        # Custody bitfield
        ('custody_bitfield', bytes_sedes),
        # Slot the attestation was included
        ('inclusion_slot', uint64),
    ]

    def __init__(self,
                 data: AttestationData,
                 aggregation_bitfield: Bitfield,
                 custody_bitfield: Bitfield,
                 inclusion_slot: Slot) -> None:
        super().__init__(
            data=data,
            aggregation_bitfield=aggregation_bitfield,
            custody_bitfield=custody_bitfield,
            inclusion_slot=inclusion_slot,
        )
