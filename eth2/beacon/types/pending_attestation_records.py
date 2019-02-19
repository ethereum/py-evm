import ssz
from ssz.sedes import (
    bytes_sedes,
    uint64,
)

from eth2.beacon.typing import (
    SlotNumber,
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
        ('slot_included', uint64),
    ]

    def __init__(self,
                 data: AttestationData,
                 aggregation_bitfield: Bitfield,
                 custody_bitfield: Bitfield,
                 slot_included: SlotNumber) -> None:
        super().__init__(
            data=data,
            aggregation_bitfield=aggregation_bitfield,
            custody_bitfield=custody_bitfield,
            slot_included=slot_included,
        )
