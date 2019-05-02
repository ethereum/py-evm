import ssz
from ssz.sedes import (
    byte_list,
    uint64,
)

from eth2.beacon.typing import (
    Slot,
    Bitfield,
)

from .attestation_data import (
    AttestationData,
)


class PendingAttestation(ssz.Serializable):

    fields = [
        # Attester aggregation bitfield
        ('aggregation_bitfield', byte_list),
        # Attestation data
        ('data', AttestationData),
        # Custody bitfield
        ('custody_bitfield', byte_list),
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
