import rlp
from rlp.sedes import (
    binary,
)

from eth.rlp.sedes import (
    uint64,
)


from .attestation_data import (
    AttestationData,
)


class PendingAttestationRecord(rlp.Serializable):
    """
    Note: using RLP until we have standardized serialization format.
    """
    fields = [
        # Signed data
        ('data', AttestationData),
        # Attester participation bitfield
        ('participation_bitfield', binary),
        # Proof of custody bitfield
        ('custody_bitfield', binary),
        # Slot in which it was included
        ('slot_included', uint64),
    ]

    def __init__(self,
                 data: AttestationData,
                 participation_bitfield: bytes,
                 custody_bitfield: bytes,
                 slot_included: int) -> None:
        super().__init__(
            data=data,
            participation_bitfield=participation_bitfield,
            custody_bitfield=custody_bitfield,
            slot_included=slot_included,
        )
